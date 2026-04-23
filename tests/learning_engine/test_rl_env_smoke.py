from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

pytest.importorskip("gymnasium")

from learning_engine.rl_env.trading_environment import (  # noqa: E402
    ConsensusWeightsReplayEnv,
    TradingReplayEnv,
)
from learning_engine.training.rl_train import (  # noqa: E402
    synthetic_ohlcv,
    train_consensus_weights_ppo,
    run_rl_smoke_episode,
)


def test_run_rl_smoke_episode_completes() -> None:
    out = run_rl_smoke_episode(max_steps=50, seed=7)
    assert out["steps"] > 0
    assert "total_reward" in out
    assert out["replay_transitions"] >= out["steps"]


def test_trading_replay_env_one_episode() -> None:
    data = synthetic_ohlcv(n=120, seed=0)
    env = TradingReplayEnv(data, window=16)
    obs, _ = env.reset(seed=0)
    assert obs.shape == env.observation_space.shape
    terminated = truncated = False
    n = 0
    while not (terminated or truncated) and n < 80:
        obs, _r, terminated, truncated, _info = env.step(env.action_space.sample())
        n += 1
    assert n > 0


def test_consensus_weights_env_softmax_action() -> None:
    closes = synthetic_ohlcv(n=100, seed=3)["close"]
    env = ConsensusWeightsReplayEnv(np.asarray(closes, dtype=np.float64), window=24)
    obs, _ = env.reset(seed=0)
    assert obs.shape == env.observation_space.shape
    a = np.array([0.1, 0.2, 0.15], dtype=np.float32)
    for _ in range(10):
        obs, _r, term, trunc, _ = env.step(a)
        if term or trunc:
            break
    assert obs.shape == env.observation_space.shape


def test_train_consensus_weights_ppo_baseline_no_crash() -> None:
    """Ohne SB3: ImportError-Pfad; mit SB3: kurzer PPO-Lauf."""
    out = train_consensus_weights_ppo(
        closes=synthetic_ohlcv(n=180, seed=9)["close"],
        total_timesteps=32,
        seed=2,
    )
    assert "algorithm" in out
    assert out["algorithm"] in ("PPO", "random_baseline")
