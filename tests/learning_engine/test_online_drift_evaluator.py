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

from learning_engine.drift.online_evaluator import (
    _shadow_champion_prob_mae,
    _signal_health_fractions,
    regime_total_variation,
)


def test_regime_total_variation_symmetric() -> None:
    base = {"trend": 0.5, "chop": 0.5}
    obs = {"trend": 30, "chop": 30}
    assert regime_total_variation(base, obs) == 0.0


def test_regime_total_variation_detects_shift() -> None:
    base = {"trend": 0.9, "chop": 0.1}
    obs = {"trend": 10, "chop": 90}
    d = regime_total_variation(base, obs)
    assert d > 0.4


def test_signal_health_fractions_counts_ood_and_missing() -> None:
    rows = [
        {"take_trade_prob": 0.5, "model_ood_alert": False, "rejection_reasons_json": []},
        {"take_trade_prob": None, "model_ood_alert": True, "rejection_reasons_json": ["online_drift_hard_block"]},
    ]
    h = _signal_health_fractions(rows)
    assert h["n"] == 2
    assert h["missing_take_trade_prob_frac"] == 0.5
    assert h["ood_alert_frac"] == 0.5
    assert h["hard_drift_tag_frac"] == 0.5


def test_shadow_champion_mae_from_snapshot() -> None:
    rows = [
        {
            "take_trade_prob": 0.8,
            "source_snapshot_json": {"take_trade_model": {"challenger_take_trade_prob": 0.6}},
        }
    ]
    mae, n = _shadow_champion_prob_mae(rows)
    assert n == 1
    assert mae == pytest.approx(0.2)
