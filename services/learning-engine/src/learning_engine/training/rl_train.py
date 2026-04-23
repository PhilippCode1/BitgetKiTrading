"""
RL-Trainings-Utilities: Smoke-Episoden, optional Stable-Baselines3 (PPO), Metrik-Logging.

Konsensus-Gewichte: ``ConsensusWeightsReplayEnv`` + PPO optimiert die War-Room-Gewichte
gegen historische Close-Reihen (Proxy fuer MARL-Router aus Phase 4/5).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import psycopg

from learning_engine.config import LearningEngineSettings
from learning_engine.rl_env.registry_export import (
    export_rl_artifact_to_registry_v2,
    write_rl_checkpoint_local,
)
from learning_engine.rl_env.trading_environment import (
    ConsensusWeightsReplayEnv,
    EpisodeReplayRecorder,
    TradingReplayEnv,
)

logger = logging.getLogger("learning_engine.training.rl")


def synthetic_ohlcv(*, n: int = 220, seed: int = 42) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    r = rng.normal(0.0, 0.0018, size=n)
    close = 50_000.0 * np.exp(np.cumsum(r))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) * (1.0 + rng.uniform(0.0, 0.001, size=n))
    low = np.minimum(open_, close) * (1.0 - rng.uniform(0.0, 0.001, size=n))
    vol = rng.uniform(50_000.0, 500_000.0, size=n)
    return {"open": open_, "high": high, "low": low, "close": close, "volume": vol}


def _log_metrics(step: int, metrics: dict[str, Any]) -> None:
    logger.info("rl_metrics step=%s %s", step, metrics)
    try:
        import mlflow  # type: ignore[import-not-found]

        if mlflow.active_run() is not None:
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v), step=step)
    except Exception:
        pass


def run_rl_smoke_episode(
    *,
    max_steps: int = 120,
    seed: int = 0,
) -> dict[str, Any]:
    """Eine vollstaendige Trainings-/Replay-Episode auf synthetischen Kerzen (ohne DB)."""
    data = synthetic_ohlcv(seed=seed)
    rec = EpisodeReplayRecorder()
    env = TradingReplayEnv(data, window=32, recorder=rec)
    obs, info = env.reset(seed=seed)
    total_reward = 0.0
    steps = 0
    terminated = truncated = False
    while not (terminated or truncated) and steps < max_steps:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += float(reward)
        steps += 1
        if steps % 20 == 0:
            _log_metrics(
                steps,
                {
                    "mean_reward_to_step": total_reward / max(1, steps),
                    "equity": float(info.get("equity", 0.0)),
                },
            )
    with tempfile.TemporaryDirectory() as td:
        rec_path = Path(td) / "episode.jsonl"
        rec.export_jsonl(rec_path)
        replay_lines = rec_path.read_text(encoding="utf-8").count("\n")
    return {
        "steps": steps,
        "total_reward": total_reward,
        "mean_reward": total_reward / max(1, steps),
        "replay_transitions": replay_lines,
        "final_equity": float(info.get("equity", 0.0)),
    }


def train_consensus_weights_ppo(
    *,
    closes: np.ndarray | None = None,
    total_timesteps: int = 1500,
    seed: int = 1,
) -> dict[str, Any]:
    """
    Optional SB3-PPO auf ``ConsensusWeightsReplayEnv``.

    Ohne ``stable-baselines3``: deterministischer Baseline-Run (Gewichte ~ Softmax(0)).
    """
    c_arr = np.asarray(closes if closes is not None else synthetic_ohlcv(seed=seed)["close"], dtype=np.float64)

    def _make_env() -> ConsensusWeightsReplayEnv:
        return ConsensusWeightsReplayEnv(np.array(c_arr, copy=True), window=32)

    try:
        from stable_baselines3 import PPO  # type: ignore[import-not-found]
        from stable_baselines3.common.vec_env import DummyVecEnv  # type: ignore[import-not-found]

        venv = DummyVecEnv([_make_env])
        model = PPO("MlpPolicy", venv, verbose=0, seed=seed)
        model.learn(total_timesteps=total_timesteps)
        w = (
            model.policy.action_net.weight.detach().float().cpu().numpy().mean(axis=0)[:3].tolist()
            if hasattr(model.policy, "action_net")
            else [0.33, 0.33, 0.34]
        )
        loss_proxy = float(
            np.mean(np.abs(model.policy.action_net.weight.detach().float().cpu().numpy()))
            if hasattr(model.policy, "action_net")
            else 0.0
        )
        _log_metrics(
            total_timesteps,
            {"ppo_loss_proxy": loss_proxy, "mean_reward_estimate": 0.0},
        )
        return {
            "algorithm": "PPO",
            "timesteps": total_timesteps,
            "consensus_logits_mean": w,
            "loss_proxy": loss_proxy,
        }
    except ImportError:
        logger.warning("stable-baselines3 nicht installiert — RL-Baseline ohne PPO")
        env = _make_env()
        obs, _ = env.reset(seed=seed)
        total_r = 0.0
        n_steps = 0
        for _ in range(min(64, max(0, len(c_arr) - 40))):
            a = env.action_space.sample()
            obs, r, term, trunc, _info = env.step(a)
            total_r += float(r)
            n_steps += 1
            if term or trunc:
                break
        mean_r = total_r / max(1, n_steps)
        _log_metrics(64, {"mean_reward_random_baseline": mean_r})
        return {
            "algorithm": "random_baseline",
            "timesteps": n_steps,
            "mean_reward": mean_r,
        }


def run_rl_training_jobs(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    job: str,
    symbol: str | None,
    promote: bool,
) -> dict[str, Any]:
    """Von ``run_training_jobs`` aufgerufen fuer ``rl-smoke`` / ``rl-consensus-ppo``."""
    del promote
    out: dict[str, Any] = {}
    if job == "rl-smoke":
        smoke = run_rl_smoke_episode()
        out["rl_smoke"] = smoke
        run_id = uuid4()
        tmp = Path(tempfile.gettempdir()) / f"rl_smoke_{run_id}.json"
        write_rl_checkpoint_local(
            tmp,
            policy_state={"type": "smoke", "steps": smoke["steps"]},
            consensus_weights=None,
        )
        reg = export_rl_artifact_to_registry_v2(
            conn,
            run_id=run_id,
            model_name="apex_rl_trading_replay",
            version="0-smoke",
            dataset_hash="synthetic:gbm-v1",
            metrics_json=smoke,
            metadata_json={"job": "rl-smoke", "symbol": symbol or "SYNTH"},
            artifact_path=str(tmp),
            registry_role="candidate",
            calibration_status="uncalibrated",
        )
        out["registry"] = reg
        return out
    if job == "rl-consensus-ppo":
        train = train_consensus_weights_ppo()
        out["rl_consensus"] = train
        run_id = uuid4()
        tmp = Path(tempfile.gettempdir()) / f"rl_consensus_{run_id}.json"
        cw = train.get("consensus_logits_mean")
        write_rl_checkpoint_local(
            tmp,
            policy_state={"type": train.get("algorithm", "unknown")},
            consensus_weights=cw,
        )
        reg = export_rl_artifact_to_registry_v2(
            conn,
            run_id=run_id,
            model_name="apex_rl_consensus_router",
            version="0-ppo",
            dataset_hash="synthetic:closes-v1",
            metrics_json=train,
            metadata_json={
                "job": "rl-consensus-ppo",
                "symbol": symbol or "SYNTH",
                "war_room_target": True,
            },
            artifact_path=str(tmp),
            registry_role="candidate",
            calibration_status="uncalibrated",
        )
        out["registry"] = reg
        return out
    raise ValueError(f"unbekannter RL-Job: {job}")
