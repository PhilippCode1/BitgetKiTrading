"""
Gymnasium-kompatible Replay-Umgebung fuer RL auf Candle-Daten (analog runner_replay / tsdb.candles).

Observation Space: OHLCV + log-Renditen + optional ``apex_core``-RSI (Rust-Hotpath).
Action Space: ``MultiDiscrete`` — Order-Typ, Positions-Bucket, Exit-Horizont (Trennung Policy vs. Preis).

Reward (``compute_step_reward``):
  - Positiv: realisierter PnL-Zuwachs, Sharpe-Ratio-Aenderung (rollierend).
  - Negativ: Drawdown-Tiefe, Trade-Dauer (Latenz), Risk-Limit-Verletzung.

Episode-Replays: ``EpisodeReplayRecorder`` schreibt Schrittfolgen fuer Post-Mortem-Analysen.
"""

from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import gymnasium as gym
import numpy as np
import psycopg
from gymnasium import spaces
from psycopg.rows import dict_row

logger = logging.getLogger("learning_engine.rl_env.trading")


def fetch_replay_ohlcv_arrays(
    database_url: str,
    *,
    symbol: str,
    timeframe: str,
    from_ts_ms: int,
    to_ts_ms: int,
) -> dict[str, np.ndarray]:
    """Laedt sortierte Kerzen fuer Replay (gleiche Quelle wie ``runner_replay``)."""
    sym = symbol.upper().strip()
    tf = timeframe.strip()
    sql = """
        SELECT open, high, low, close, usdt_vol
        FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s
          AND start_ts_ms >= %s AND start_ts_ms <= %s
        ORDER BY start_ts_ms ASC, ingest_ts_ms ASC
    """
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        rows = conn.execute(sql, (sym, tf, from_ts_ms, to_ts_ms)).fetchall()
    if not rows:
        raise ValueError("keine Kerzen fuer den angegebenen Zeitraum")
    o = np.array([float(r["open"]) for r in rows], dtype=np.float64)
    h = np.array([float(r["high"]) for r in rows], dtype=np.float64)
    l = np.array([float(r["low"]) for r in rows], dtype=np.float64)
    c = np.array([float(r["close"]) for r in rows], dtype=np.float64)
    v = np.array([float(r["usdt_vol"]) for r in rows], dtype=np.float64)
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def _rsi_column(closes: np.ndarray, window: int) -> np.ndarray:
    try:
        import apex_core  # type: ignore[import-not-found]

        out = np.zeros_like(closes, dtype=np.float64)
        for i in range(len(closes)):
            start = max(0, i - window * 3)
            seg = closes[start : i + 1]
            if len(seg) < window + 1:
                out[i] = 50.0
            else:
                out[i] = float(apex_core.compute_rsi_sma(seg.astype(np.float64), window))
        return out
    except Exception:
        logger.debug("apex_core RSI nicht verfuegbar — Spalte mit 50.0 gefuellt")
        return np.full_like(closes, 50.0, dtype=np.float64)


@dataclass
class RewardWeights:
    """Gewichte fuer die Reward-Zerlegung (kalibrierbar fuer PPO/SAC)."""

    pnl: float = 1.0
    sharpe_delta: float = 0.35
    drawdown: float = 0.85
    trade_duration: float = 0.12
    risk_violation: float = 2.5
    ams_governor_block_bonus: float = 3.2
    ams_false_negative_penalty: float = 18.0


def compute_ams_governor_reward(
    *,
    ams_trap_active: bool,
    governor_blocked_trade: bool,
    weights: RewardWeights | None = None,
) -> float:
    """
    AMS-Simulation: Risk-Governor blockiert Falle -> hoher Bonus;
    Trade trotz erkanntem Stress -> massive Strafe.
    """
    if not ams_trap_active:
        return 0.0
    w = weights or RewardWeights()
    if governor_blocked_trade:
        return float(w.ams_governor_block_bonus)
    return -float(w.ams_false_negative_penalty)


def compute_step_reward(
    *,
    realized_pnl_delta: float,
    sharpe_before: float,
    sharpe_after: float,
    drawdown_depth: float,
    trade_open_steps: int,
    max_trade_horizon: int,
    risk_violation: bool,
    weights: RewardWeights | None = None,
    ams_trap_active: bool = False,
    governor_blocked_trade: bool = False,
) -> float:
    """
    Skalare Belohnung pro Schritt.

    - Positiv: ``pnl * realized_pnl_delta`` + ``sharpe_delta * max(0, sharpe_after - sharpe_before)``
    - Negativ: ``drawdown * drawdown_depth`` (0..1), Dauer-Penalty offener Trade,
      Risk-Flag (Positionslimit / Margin-Proxy).
    """
    w = weights or RewardWeights()
    r = w.pnl * float(realized_pnl_delta)
    r += w.sharpe_delta * max(0.0, float(sharpe_after - float(sharpe_before)))
    r -= w.drawdown * max(0.0, min(1.0, float(drawdown_depth)))
    if max_trade_horizon > 0 and trade_open_steps > 0:
        r -= w.trade_duration * (float(trade_open_steps) / float(max_trade_horizon))
    if risk_violation:
        r -= w.risk_violation
    r += compute_ams_governor_reward(
        ams_trap_active=ams_trap_active,
        governor_blocked_trade=governor_blocked_trade,
        weights=w,
    )
    return float(r)


def _rolling_sharpe(returns: np.ndarray, window: int) -> float:
    if len(returns) < 3:
        return 0.0
    r = returns[-window:]
    mu = float(np.mean(r))
    sd = float(np.std(r))
    if sd < 1e-12:
        return 0.0
    return (mu / sd) * math.sqrt(max(1, len(r)))


@dataclass
class EpisodeReplayRecorder:
    """Speichert Transitions fuer fehlgeschlagene Policy-Analysen (JSONL)."""

    steps: list[dict[str, Any]] = field(default_factory=list)

    def record(
        self,
        *,
        t: int,
        obs: np.ndarray,
        action: np.ndarray | int | tuple[Any, ...],
        reward: float,
        info: dict[str, Any],
    ) -> None:
        self.steps.append(
            {
                "t": int(t),
                "obs_digest": float(np.mean(obs)) if obs.size else 0.0,
                "action": np.asarray(action).tolist()
                if not isinstance(action, (int, float))
                else action,
                "reward": float(reward),
                "info": {k: v for k, v in info.items() if k != "raw_obs"},
            }
        )

    def export_jsonl(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in self.steps:
                fh.write(json.dumps(row, default=str) + "\n")


class TradingReplayEnv(gym.Env):
    """
    Ein Schritt = eine Kerze. Portfolio in Einheitswaehrung (Start 1.0).

    action: ``MultiDiscrete([4, 5, 16])`` = [order, size_bucket, exit_horizon_bars]
      - order: 0 hold, 1 long, 2 short, 3 flatten
      - size_bucket: 0..4 skaliert Positionsfraktion
      - exit_horizon: max Haltedauer bis Flat-Zwang
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        ohlcv: dict[str, np.ndarray],
        *,
        window: int = 32,
        fee_bps: float = 5.0,
        max_position_frac: float = 0.95,
        reward_weights: RewardWeights | None = None,
        recorder: EpisodeReplayRecorder | None = None,
        ams_simulation_mode: bool = False,
        ams_attack_probability: float = 0.14,
        ams_rng_seed: int | None = None,
    ) -> None:
        super().__init__()
        self._closes = np.asarray(ohlcv["close"], dtype=np.float64)
        n = len(self._closes)
        if n < window + 5:
            raise ValueError("zu wenig Kerzen fuer gewaehltes Fenster")
        self._o = np.asarray(ohlcv["open"], dtype=np.float64)
        self._h = np.asarray(ohlcv["high"], dtype=np.float64)
        self._l = np.asarray(ohlcv["low"], dtype=np.float64)
        self._v = np.asarray(ohlcv["volume"], dtype=np.float64)
        self._window = int(window)
        self._fee = float(fee_bps) / 10_000.0
        self._max_pos = float(max_position_frac)
        self._w = reward_weights or RewardWeights()
        self._rec = recorder
        self._ams_sim = bool(ams_simulation_mode)
        self._ams_p = float(max(0.0, min(1.0, ams_attack_probability)))
        self._ams_rng = random.Random(int(ams_rng_seed) if ams_rng_seed is not None else None)

        self._rsi = _rsi_column(self._closes, 14)
        self._n_feat = 7  # OHLCV + logret + rsi_norm
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self._window, self._n_feat),
            dtype=np.float32,
        )
        self.action_space = spaces.MultiDiscrete([4, 5, 16])

        self._t = 0
        self._equity = 1.0
        self._pos_frac = 0.0
        self._entry_step = 0
        self._horizon_flat = 0
        self._returns_hist: list[float] = []
        self._peak_equity = 1.0
        self._max_dd = 0.0
        self._last_sharpe = 0.0

    @classmethod
    def from_database(
        cls,
        database_url: str,
        *,
        symbol: str,
        timeframe: str,
        from_ts_ms: int,
        to_ts_ms: int,
        **kwargs: Any,
    ) -> TradingReplayEnv:
        arrays = fetch_replay_ohlcv_arrays(
            database_url,
            symbol=symbol,
            timeframe=timeframe,
            from_ts_ms=from_ts_ms,
            to_ts_ms=to_ts_ms,
        )
        return cls(arrays, **kwargs)

    def _obs_at(self, t: int) -> np.ndarray:
        start = t - self._window + 1
        sl = slice(start, t + 1)
        c = self._closes[sl]
        logret = np.zeros_like(c)
        logret[1:] = np.log(c[1:] / np.maximum(c[:-1], 1e-12))
        o = self._o[sl]
        h = self._h[sl]
        l = self._l[sl]
        v = np.log1p(self._v[sl])
        rsi_n = (self._rsi[sl] - 50.0) / 50.0
        mat = np.stack([o, h, l, c, v, logret, rsi_n], axis=-1).astype(np.float32)
        return mat

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._t = self._window
        self._equity = 1.0
        self._pos_frac = 0.0
        self._entry_step = 0
        self._horizon_flat = 0
        self._returns_hist = []
        self._peak_equity = 1.0
        self._max_dd = 0.0
        self._last_sharpe = 0.0
        if self._rec:
            self._rec.steps.clear()
        obs = self._obs_at(self._t)
        return obs, {"t": self._t, "equity": self._equity}

    def step(self, action: np.ndarray | tuple[int, ...]) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._t >= len(self._closes) - 2:
            return self._obs_at(self._t), 0.0, True, False, {"reason": "end_of_data"}

        a = np.asarray(action, dtype=np.int64).ravel()
        order = int(a[0]) if len(a) > 0 else 0
        size_b = int(a[1]) if len(a) > 1 else 0
        horizon = int(a[2]) if len(a) > 2 else 0
        price = float(self._closes[self._t])
        next_price = float(self._closes[self._t + 1])

        size_frac = min(self._max_pos, (0.05 + 0.15 * float(size_b)) * 0.25)

        prev_pos = float(self._pos_frac)
        if order == 3 or (
            self._horizon_flat > 0
            and self._entry_step > 0
            and (self._t - self._entry_step) >= self._horizon_flat
        ):
            target = 0.0
        elif order == 1:
            target = size_frac
        elif order == 2:
            target = -size_frac
        else:
            target = prev_pos

        risk_violation = abs(target) > self._max_pos + 1e-9
        if risk_violation:
            target = float(np.sign(target) * self._max_pos)

        mkt_ret = next_price / max(price, 1e-12) - 1.0
        pnl_frac = prev_pos * mkt_ret
        turn = abs(target - prev_pos)
        fee_cost = self._fee * turn
        pre_equity = self._equity
        self._equity *= 1.0 + pnl_frac - fee_cost
        self._equity = max(1e-9, float(self._equity))
        realized_pnl_delta = float(self._equity - pre_equity)

        self._pos_frac = target
        if target != 0.0 and (target != prev_pos or self._entry_step == 0):
            self._entry_step = self._t
            self._horizon_flat = max(1, int(horizon))
        if target == 0.0:
            self._entry_step = 0
            self._horizon_flat = 0

        trade_open_steps = 0
        if self._pos_frac != 0.0 and self._entry_step > 0:
            trade_open_steps = self._t - self._entry_step

        self._peak_equity = max(self._peak_equity, self._equity)
        dd = 1.0 - (self._equity / max(self._peak_equity, 1e-12))
        self._max_dd = max(self._max_dd, dd)

        ret = realized_pnl_delta / max(pre_equity, 1e-12)
        self._returns_hist.append(float(ret))
        sharpe_after = _rolling_sharpe(np.asarray(self._returns_hist, dtype=np.float64), min(64, len(self._returns_hist)))
        sharpe_before = self._last_sharpe
        self._last_sharpe = sharpe_after

        ams_trap = bool(
            self._ams_sim and self._ams_rng.random() < self._ams_p and self._t > self._window + 2
        )
        opened = order in (1, 2) and abs(prev_pos) < 1e-9 and abs(target) > 1e-9
        governor_blocked = ams_trap and not opened

        reward = compute_step_reward(
            realized_pnl_delta=realized_pnl_delta,
            sharpe_before=sharpe_before,
            sharpe_after=sharpe_after,
            drawdown_depth=self._max_dd,
            trade_open_steps=trade_open_steps,
            max_trade_horizon=max(1, self._horizon_flat),
            risk_violation=risk_violation,
            weights=self._w,
            ams_trap_active=ams_trap,
            governor_blocked_trade=governor_blocked,
        )

        self._t += 1
        terminated = self._t >= len(self._closes) - 2
        obs = self._obs_at(self._t)
        info: dict[str, Any] = {
            "t": self._t,
            "equity": self._equity,
            "drawdown": self._max_dd,
            "risk_violation": risk_violation,
            "sharpe": sharpe_after,
            "ams_simulation": self._ams_sim,
            "ams_trap": ams_trap,
            "ams_governor_blocked": governor_blocked,
        }
        if self._rec:
            self._rec.record(t=self._t, obs=obs, action=tuple(int(x) for x in a[:3]), reward=reward, info=info)
        return obs, reward, terminated, False, info


class ConsensusWeightsReplayEnv(gym.Env):
    """
    Optimiert die drei War-Room-Gewichte (Macro/Quant/Risk) gegen dieselbe Kerzenreihe.

    Observation: letzte Renditen + Volatilitaet + Drawdown-Proxy.
    Action: ``Box(3,)`` — Logits, intern per Softmax zu Gewichten normalisiert.
    Reward: Log-Rendite eines simplen virtuellen Committees gesteuert durch die Gewichte.
    """

    metadata = {"render_modes": []}

    def __init__(self, closes: np.ndarray, *, window: int = 32) -> None:
        super().__init__()
        self._c = np.asarray(closes, dtype=np.float64)
        if len(self._c) < window + 5:
            raise ValueError("zu wenig Daten")
        self._w = int(window)
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(self._w + 2,), dtype=np.float32
        )
        self.action_space = spaces.Box(low=-2.0, high=2.0, shape=(3,), dtype=np.float32)
        self._t = 0

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, Any] | None = None,
    ) -> tuple[np.ndarray, dict[str, Any]]:
        super().reset(seed=seed)
        self._t = self._w
        return self._obs(), {"t": self._t}

    def _obs(self) -> np.ndarray:
        sl = slice(self._t - self._w + 1, self._t + 1)
        r = np.diff(np.log(np.maximum(self._c[sl], 1e-12)))
        pad = self._w - len(r)
        if pad > 0:
            r = np.pad(r, (pad, 0))
        vol = float(np.std(r))
        dd = float(np.max(self._c[: self._t + 1]) - self._c[self._t]) / max(
            float(np.max(self._c[: self._t + 1])), 1e-12
        )
        out = np.concatenate([r.astype(np.float32), np.array([vol, dd], dtype=np.float32)])
        return out

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
        if self._t >= len(self._c) - 2:
            return self._obs(), 0.0, True, False, {}

        logits = np.asarray(action, dtype=np.float64).ravel()[:3]
        ex = np.exp(logits - np.max(logits))
        weights = ex / np.sum(ex)

        sl = slice(max(0, self._t - 8), self._t + 1)
        roc = (
            (self._c[self._t] - self._c[self._t - 5]) / max(self._c[self._t - 5], 1e-12)
            if self._t >= 5
            else 0.0
        )
        macro_z = float(np.sign(self._c[self._t] - self._c[self._t - 1]))
        quant_z = float(np.tanh(roc * 10.0))
        vol_s = float(np.std(np.diff(np.log(self._c[sl] + 1e-12))))
        risk_z = -1.0 if vol_s > 0.01 else 1.0
        score = float(weights[0] * macro_z + weights[1] * quant_z + weights[2] * risk_z)
        p0 = self._c[self._t]
        p1 = self._c[self._t + 1]
        mkt_ret = math.log(p1 / max(p0, 1e-12))
        aligned = mkt_ret * (1.0 if score > 0.15 else -1.0 if score < -0.15 else 0.0)
        reward = float(aligned) - 0.25 * abs(weights[0] - 0.33)

        self._t += 1
        terminated = self._t >= len(self._c) - 2
        return self._obs(), reward, terminated, False, {"weights": weights.tolist(), "score": score}
