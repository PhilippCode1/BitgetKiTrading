from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (LEARNING_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from learning_engine.config import LearningEngineSettings
from learning_engine.registry_v2.champion_promotion_gates import (
    evaluate_champion_challenger_backtest_gate,
    evaluate_champion_promotion_gates,
)
from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME


def _backtest_meta_ok() -> dict:
    return {
        "champion_challenger_backtest": {
            "n_simulated_trades": 500,
            "champion": {
                "sharpe_ratio": 1.0,
                "max_drawdown": 0.12,
                "win_rate": 0.50,
            },
            "challenger": {
                "sharpe_ratio": 1.11,
                "max_drawdown": 0.12,
                "win_rate": 0.51,
            },
        }
    }


@pytest.fixture
def settings_backtest_on(monkeypatch: pytest.MonkeyPatch) -> LearningEngineSettings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_CHALLENGER_CHAMPION_BACKTEST_GATE_ENABLED", "true")
    return LearningEngineSettings()


def test_backtest_passes_rel_sharpe_10pct(settings_backtest_on: LearningEngineSettings) -> None:
    r = evaluate_champion_challenger_backtest_gate(
        metadata_json=_backtest_meta_ok(),
        settings=settings_backtest_on,
    )
    assert r.ok
    assert (r.details.get("champion_challenger_backtest") or {}).get("pass") is True


def test_backtest_fails_too_few_trades(settings_backtest_on: LearningEngineSettings) -> None:
    m = _backtest_meta_ok()
    m["champion_challenger_backtest"]["n_simulated_trades"] = 499
    r = evaluate_champion_challenger_backtest_gate(metadata_json=m, settings=settings_backtest_on)
    assert not r.ok
    assert "champion_challenger_backtest_n_trades_below_minimum" in r.reasons


def test_backtest_fails_worse_drawdown(settings_backtest_on: LearningEngineSettings) -> None:
    m = _backtest_meta_ok()
    m["champion_challenger_backtest"]["challenger"]["max_drawdown"] = 0.20
    r = evaluate_champion_challenger_backtest_gate(metadata_json=m, settings=settings_backtest_on)
    assert not r.ok
    assert "challenger_max_drawdown_worse_than_champion" in r.reasons


def test_promotion_gates_merges_backtest_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("MODEL_PROMOTION_GATES_ENABLED", "true")
    monkeypatch.setenv("MODEL_CHALLENGER_CHAMPION_BACKTEST_GATE_ENABLED", "true")
    s = LearningEngineSettings()
    mj = {
        "cv_summary": {
            "walk_forward_mean_roc_auc": 0.75,
            "purged_kfold_mean_roc_auc": 0.74,
        },
        "roc_auc": 0.72,
        "brier_score": 0.18,
    }
    r = evaluate_champion_promotion_gates(
        model_name=TAKE_TRADE_MODEL_NAME,
        metrics_json=mj,
        metadata_json=_backtest_meta_ok(),
        settings=s,
    )
    assert r.ok
    assert (r.details.get("champion_challenger_backtest") or {}).get("pass") is True
