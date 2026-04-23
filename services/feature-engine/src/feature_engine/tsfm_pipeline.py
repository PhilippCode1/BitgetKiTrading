"""
Zero-Shot Patch-Pipeline: Tick-Puffer, Log-Returns + rollierender Z-Score, gRPC -> TimesFM, Eventbus.

Stale-Gate: max. Luecke zwischen Ticks im Puffer; optional Online-Drift aus ``learn.online_drift_state``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

import numpy as np
import psycopg
from psycopg import errors as pg_errors

from shared_py.eventbus import (
    ConsumedEvent,
    EventEnvelope,
    STREAM_TSFM_SIGNAL_CANDIDATE,
    make_stream_bus_from_url,
)
from shared_py.online_drift import action_rank, normalize_online_drift_action
from shared_py.timesfm_client import TimesFmGrpcClient

try:
    import apex_core as _apex_core  # type: ignore[import-not-found]
except ImportError:
    _apex_core = None

try:
    from numba import njit
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(*_a: Any, **_k: Any) -> Any:  # type: ignore[misc]
        def _wrap(f: Any) -> Any:
            return f

        return _wrap
else:
    _NUMBA_AVAILABLE = True


MAX_TICKS_PER_SYMBOL = 100_000


@dataclass(slots=True)
class _Tick:
    ts_ms: int
    price: float


class TickBuffer:
    """Ringpuffer (Deque) pro Symbol, max. ``MAX_TICKS_PER_SYMBOL`` Eintraege."""

    def __init__(self, *, maxlen: int = MAX_TICKS_PER_SYMBOL) -> None:
        self._maxlen = int(max(1000, min(maxlen, MAX_TICKS_PER_SYMBOL)))
        self._buf: dict[str, deque[_Tick]] = {}

    def _deque_for(self, symbol: str) -> deque[_Tick]:
        d = self._buf.get(symbol)
        if d is None:
            d = deque(maxlen=self._maxlen)
            self._buf[symbol] = d
        return d

    def append(self, symbol: str, ts_ms: int, price: float) -> None:
        if price <= 0.0 or not np.isfinite(price):
            return
        self._deque_for(symbol).append(_Tick(ts_ms=int(ts_ms), price=float(price)))

    def last_gap_ms(self, symbol: str) -> int | None:
        """Luecke zwischen vorletztem und letztem Tick (ms)."""
        d = self._buf.get(symbol)
        if d is None or len(d) < 2:
            return None
        return int(d[-1].ts_ms - d[-2].ts_ms)

    def tail_prices(self, symbol: str, n: int) -> np.ndarray | None:
        """Letzte ``n`` Preise float64 (aeste -> juengste)."""
        d = self._buf.get(symbol)
        if d is None or len(d) < n:
            return None
        out = np.empty(n, dtype=np.float64)
        it = iter(d)
        # Deque ist ordered oldest->newest; skip to last n
        skip = len(d) - n
        for _ in range(skip):
            next(it, None)
        for i, t in enumerate(it):
            out[i] = t.price
        return out


def _rolling_zscore_numpy(x: np.ndarray, win: int) -> np.ndarray:
    n = x.shape[0]
    out = np.zeros(n, dtype=np.float64)
    for i in range(n):
        lo = max(0, i - win + 1)
        seg = x[lo : i + 1]
        m = float(seg.mean())
        s = float(seg.std(ddof=1)) if seg.size > 1 else 0.0
        out[i] = 0.0 if s < 1e-12 else (float(x[i]) - m) / s
    return out


if _NUMBA_AVAILABLE:

    @njit(cache=True)
    def _rolling_zscore_numba(x: np.ndarray, win: int) -> np.ndarray:
        n = x.shape[0]
        out = np.empty(n, dtype=np.float64)
        for i in range(n):
            lo = i - win + 1
            if lo < 0:
                lo = 0
            s = 0.0
            ss = 0.0
            cnt = 0
            for j in range(lo, i + 1):
                v = x[j]
                s += v
                ss += v * v
                cnt += 1
            m = s / cnt
            var = ss / cnt - m * m
            if var < 1e-24:
                out[i] = 0.0
            else:
                out[i] = (x[i] - m) / var**0.5
        return out
else:

    def _rolling_zscore_numba(x: np.ndarray, win: int) -> np.ndarray:
        return _rolling_zscore_numpy(x, win)


def rolling_zscore_window_vec(x: np.ndarray, win: int) -> np.ndarray:
    """O(n) rollierender Z-Score (Welford-aehnlich ueber Praefixsummen)."""
    v = np.asarray(x, dtype=np.float64)
    n = v.size
    if n == 0:
        return v
    w = max(1, min(int(win), n))
    pref = np.empty(n + 1, dtype=np.float64)
    pref[0] = 0.0
    np.cumsum(v, out=pref[1:])
    pref2 = np.empty(n + 1, dtype=np.float64)
    pref2[0] = 0.0
    np.cumsum(v * v, out=pref2[1:])
    idx = np.arange(n, dtype=np.int64)
    lo = np.maximum(0, idx - w + 1)
    cnt = (idx - lo + 1).astype(np.float64)
    s = pref[idx + 1] - pref[lo]
    ss = pref2[idx + 1] - pref2[lo]
    m = s / cnt
    var = np.maximum(ss / cnt - m * m, 0.0)
    std = np.sqrt(var)
    std = np.maximum(std, 1e-12)
    return (v - m) / std


def log_returns_from_prices(prices: np.ndarray) -> np.ndarray:
    """``prices`` shape (n+1,) -> ``n`` Log-Returns."""
    p = np.asarray(prices, dtype=np.float64)
    if p.size < 2:
        return np.zeros(0, dtype=np.float64)
    return np.diff(np.log(p))


def apex_volatility_floor(returns: np.ndarray, *, ema_span: int) -> float:
    """Rust-Core: EMA(|r|) als Volatilitaetsboden fuer die Skalierung."""
    absr = np.abs(np.asarray(returns, dtype=np.float64))
    if absr.size == 0:
        return 1e-12
    if _apex_core is not None and ema_span > 1:
        try:
            return max(1e-12, float(_apex_core.compute_ema_last(absr, int(ema_span))))
        except Exception:
            pass
    return max(1e-12, float(np.std(absr)) if absr.size > 1 else float(absr[-1]))


def build_timesfm_context_vector(
    prices_tail: np.ndarray,
    *,
    context_len: int,
    rolling_z_window: int,
    use_numba: bool,
) -> np.ndarray:
    """
    Baut Eingabevektor Laenge ``context_len`` (float32) aus den letzten Preisen.

    Schritte: Log-Returns aus ``context_len+1`` Preisen -> rollierender Z-Score ->
    abschliessend Division durch (Vol-Boden aus apex_core EMA(|r|)) fuer Stabilitaet.
    """
    need = int(context_len) + 1
    pt = np.asarray(prices_tail[-need:], dtype=np.float64)
    lr = log_returns_from_prices(pt)
    if lr.size != int(context_len):
        raise ValueError("log-return Laenge passt nicht zu context_len")
    w = max(8, min(int(rolling_z_window), lr.size))
    if use_numba and _NUMBA_AVAILABLE:
        rz = _rolling_zscore_numba(lr, w)
    else:
        rz = rolling_zscore_window_vec(lr, w)
    floor = apex_volatility_floor(lr, ema_span=min(64, max(8, w // 2)))
    scaled = rz / max(floor, 1e-12)
    return scaled.astype(np.float32)


def prepare_context_under_ms(
    buffer: TickBuffer,
    symbol: str,
    *,
    context_len: int,
    rolling_z_window: int,
    use_numba: bool,
    budget_ms: float = 5.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """
    Extrahiert Tail, transformiert. Akzeptanz: typisch << ``budget_ms`` fuer 100k-Puffer
    (nur letzte ``context_len+1`` Preise werden gelesen).
    """
    t0 = time.perf_counter()
    tail = buffer.tail_prices(symbol, int(context_len) + 1)
    if tail is None:
        raise ValueError("insufficient_ticks")
    vec = build_timesfm_context_vector(
        tail,
        context_len=int(context_len),
        rolling_z_window=int(rolling_z_window),
        use_numba=use_numba,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    meta = {"prepare_context_ms": float(elapsed_ms)}
    if elapsed_ms > budget_ms:
        raise RuntimeError(f"tsfm_context_prepare_slow_ms={elapsed_ms:.3f}")
    return vec, meta


def forecast_confidence_metrics(forecast: np.ndarray) -> dict[str, float]:
    """
    Konfidenz aus Patch-Varianz: niedrige Varianz der Inkremente -> hoehere Konfidenz.
    """
    fc = np.asarray(forecast, dtype=np.float64).reshape(-1)
    if fc.size < 2:
        return {"confidence_0_1": 0.5, "patch_variance": 0.0, "patch_incr_std": 0.0}
    d = np.diff(fc)
    incr_std = float(np.std(d, ddof=1)) if d.size > 1 else 0.0
    var = float(np.var(fc, ddof=1)) if fc.size > 1 else 0.0
    conf = float(1.0 / (1.0 + incr_std * 50.0 + var * 10.0))
    conf = max(0.0, min(1.0, conf))
    return {
        "confidence_0_1": conf,
        "patch_variance": var,
        "patch_incr_std": incr_std,
    }


def _read_online_drift_action_sync(database_url: str) -> str | None:
    try:
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            row = conn.execute(
                "SELECT effective_action FROM learn.online_drift_state WHERE scope = %s",
                ("global",),
            ).fetchone()
    except (pg_errors.UndefinedTable, OSError, psycopg.Error):
        return None
    if not row:
        return None
    return str(row[0])


def online_drift_blocks_prediction(
    database_url: str,
    *,
    min_rank_to_block: int,
) -> bool:
    """
    True, wenn Online-Drift mindestens ``min_rank_to_block`` erreicht
    (Rang siehe ``shared_py.online_drift.action_rank``).
    """
    raw = _read_online_drift_action_sync(database_url)
    if raw is None:
        return False
    act = normalize_online_drift_action(raw)
    return action_rank(act) >= int(min_rank_to_block)


class TsfmPatchConsumer:
    """
    Konsumiert ``events:market_tick``, aktualisiert ``TickBuffer``, ruft Inference auf,
    publiziert ``tsfm_signal_candidate``.
    """

    def __init__(self, settings: Any, *, logger: logging.Logger | None = None) -> None:
        self._settings = settings
        self._logger = logger or logging.getLogger("feature_engine.tsfm")
        self._stop = asyncio.Event()
        self._buffer = TickBuffer(maxlen=MAX_TICKS_PER_SYMBOL)
        self._tick_phase: dict[str, int] = defaultdict(int)
        self._bus = make_stream_bus_from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
            logger=self._logger,
        )

    async def stop(self) -> None:
        self._stop.set()

    async def close(self) -> None:
        await asyncio.to_thread(self._bus.close)

    async def run(self) -> None:
        self._logger.info(
            "tsfm patch consumer gestartet stream=%s group=%s stride=%s target=%s",
            self._settings.tsfm_tick_stream,
            self._settings.tsfm_tick_group,
            self._settings.tsfm_tick_stride,
            self._settings.tsfm_inference_grpc_target,
        )
        try:
            while not self._stop.is_set():
                try:
                    await asyncio.to_thread(
                        self._bus.ensure_group,
                        self._settings.tsfm_tick_stream,
                        self._settings.tsfm_tick_group,
                    )
                    items = await asyncio.to_thread(
                        self._bus.consume,
                        self._settings.tsfm_tick_stream,
                        self._settings.tsfm_tick_group,
                        self._settings.tsfm_tick_consumer,
                        self._settings.eventbus_default_count,
                        self._settings.eventbus_default_block_ms,
                    )
                    if not items:
                        continue
                    for item in items:
                        await self._handle_item(item)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._logger.warning("tsfm consumer loop error: %s", exc)
                    await asyncio.sleep(1.0)
        finally:
            await self.close()

    async def _handle_item(self, item: ConsumedEvent) -> None:
        env = item.envelope
        if env.event_type != "market_tick":
            await self._ack(item)
            return
        symbol = (env.symbol or "").strip().upper()
        if not symbol:
            await self._ack(item)
            return
        payload = env.payload if isinstance(env.payload, dict) else {}
        ts_ms = int(env.exchange_ts_ms or payload.get("ts_ms") or 0)
        price = _extract_tick_price(payload)
        if price is None or ts_ms <= 0:
            await self._ack(item)
            return
        self._buffer.append(symbol, ts_ms, price)
        self._tick_phase[symbol] += 1
        if self._tick_phase[symbol] % int(self._settings.tsfm_tick_stride) != 0:
            await self._ack(item)
            return
        gap = self._buffer.last_gap_ms(symbol)
        if gap is not None and gap > int(self._settings.tsfm_max_tick_gap_ms):
            self._logger.debug(
                "tsfm stale_gap skip symbol=%s gap_ms=%s max=%s",
                symbol,
                gap,
                self._settings.tsfm_max_tick_gap_ms,
            )
            await self._ack(item)
            return
        if int(self._settings.tsfm_online_drift_min_rank_to_block) > 0:
            blocked = await asyncio.to_thread(
                online_drift_blocks_prediction,
                self._settings.database_url,
                min_rank_to_block=int(self._settings.tsfm_online_drift_min_rank_to_block),
            )
            if blocked:
                self._logger.debug("tsfm online_drift_block skip symbol=%s", symbol)
                await self._ack(item)
                return
        try:
            vec, prep_meta = prepare_context_under_ms(
                self._buffer,
                symbol,
                context_len=int(self._settings.tsfm_context_len),
                rolling_z_window=int(self._settings.tsfm_rolling_z_window),
                use_numba=bool(self._settings.tsfm_use_numba),
                budget_ms=float(self._settings.tsfm_prepare_budget_ms),
            )
        except (ValueError, RuntimeError) as exc:
            self._logger.debug("tsfm prepare skip symbol=%s err=%s", symbol, exc)
            await self._ack(item)
            return
        try:
            forecasts = await predict_timesfm_patch(
                self._settings.tsfm_inference_grpc_target,
                vec,
                forecast_horizon=int(self._settings.tsfm_forecast_horizon),
                model_id=str(self._settings.tsfm_model_id),
            )
        except Exception as exc:
            self._logger.warning("tsfm grpc predict failed symbol=%s err=%s", symbol, exc)
            await self._ack(item)
            return
        fc = forecasts[0] if forecasts else None
        if fc is None or fc.size == 0:
            await self._ack(item)
            return
        metrics = forecast_confidence_metrics(fc)
        f32b = fc.astype(np.float32).tobytes()
        digest = hashlib.sha256(f32b).hexdigest()
        preview = [float(x) for x in fc[: min(8, fc.size)]]
        out_env = EventEnvelope(
            event_type="tsfm_signal_candidate",
            symbol=symbol,
            instrument=env.instrument,
            timeframe="tick",
            exchange_ts_ms=ts_ms,
            dedupe_key=f"tsfm_candidate:{symbol}:{ts_ms}:{digest[:16]}",
            payload={
                "schema": "tsfm_signal_candidate/v1",
                "source_ts_ms": ts_ms,
                "context_len": int(self._settings.tsfm_context_len),
                "forecast_horizon": int(fc.size),
                "forecast_sha256": digest,
                "forecast_preview": preview,
                "prep_meta": prep_meta,
                "confidence_0_1": metrics["confidence_0_1"],
                "patch_variance": metrics["patch_variance"],
                "patch_incr_std": metrics["patch_incr_std"],
                "model_id": str(self._settings.tsfm_model_id),
            },
            trace={
                "source": "feature_engine.tsfm_pipeline",
                "grpc_target": self._settings.tsfm_inference_grpc_target,
            },
        )
        try:
            await asyncio.to_thread(
                self._bus.publish,
                STREAM_TSFM_SIGNAL_CANDIDATE,
                out_env,
            )
            self._logger.info(
                "tsfm_signal_candidate published symbol=%s horizon=%s conf=%.4f",
                symbol,
                fc.size,
                metrics["confidence_0_1"],
            )
        except Exception as exc:
            self._logger.warning("tsfm publish failed symbol=%s err=%s", symbol, exc)
        await self._ack(item)

    async def _ack(self, item: ConsumedEvent) -> None:
        await asyncio.to_thread(
            self._bus.ack,
            item.stream,
            self._settings.tsfm_tick_group,
            item.message_id,
        )


def _extract_tick_price(payload: dict[str, Any]) -> float | None:
    for key in ("mark_price", "last_pr", "last_price", "mid"):
        v = payload.get(key)
        if v is None:
            continue
        try:
            x = float(v)
        except (TypeError, ValueError):
            continue
        if np.isfinite(x) and x > 0:
            return x
    bid = payload.get("bid_pr")
    ask = payload.get("ask_pr")
    try:
        b = float(bid) if bid is not None else None
        a = float(ask) if ask is not None else None
    except (TypeError, ValueError):
        return None
    if b is not None and a is not None and b > 0 and a > 0:
        return float((b + a) * 0.5)
    return None


async def predict_timesfm_patch(
    grpc_target: str,
    context_vector: np.ndarray,
    *,
    forecast_horizon: int,
    model_id: str,
) -> list[np.ndarray]:
    """Ein Batch mit einer Serie (``context_vector`` als Preis-Proxy-Zeitreihe)."""
    async with TimesFmGrpcClient(grpc_target) as client:
        return await client.predict_batch(
            [("tsfm_ctx", context_vector)],
            forecast_horizon=int(forecast_horizon),
            model_id=model_id,
            timeout_sec=30.0,
        )
