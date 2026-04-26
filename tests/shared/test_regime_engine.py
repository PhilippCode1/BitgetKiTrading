from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.regime_engine import (
    REGIME_ENGINE_VERSION,
    RegimeEngineInputs,
    classify_regime,
)


def _base_ctx() -> dict:
    return {
        "timeframe": "5m",
        "analysis_ts_ms": 1_700_000_000_000,
        "structure_state": {"trend_dir": "RANGE", "compression_flag": False, "breakout_box_json": {}},
        "structure_events": [],
        "primary_feature": {},
        "features_by_tf": {"15m": {"trend_dir": 0}, "1H": {"trend_dir": 0}, "4H": {"trend_dir": 0}},
        "news_row": None,
        "news_shock_feature_enabled": True,
    }


def test_dislocation_without_news_three_stress_signals() -> None:
    ctx = _base_ctx()
    ctx["primary_feature"] = {
        "vol_z_50": 2.1,
        "atrp_14": 0.19,
        "spread_bps": 11.0,
    }
    inp = RegimeEngineInputs(**ctx)
    r = classify_regime(inp)
    assert r.market_regime == "dislocation"
    assert r.regime_state == "low_liquidity"
    assert r.regime_substate == "low_liquidity_dislocation_stack"
    assert r.regime_snapshot["regime_engine_version"] == REGIME_ENGINE_VERSION
    assert r.regime_state
    assert r.regime_transition_state


def test_shock_from_news_even_without_extra_micro() -> None:
    ctx = _base_ctx()
    ctx["primary_feature"] = {"range_score": 40.0, "atrp_14": 0.05}
    ctx["news_row"] = {
        "relevance_score": 78.0,
        "sentiment": "bearish",
        "impact_window": "immediate",
    }
    inp = RegimeEngineInputs(**ctx)
    r = classify_regime(inp)
    assert r.market_regime == "shock"
    assert r.regime_substate == "shock_news_event"


def test_trend_to_chop_on_choch_churn() -> None:
    ts = 1_700_000_000_000
    events = [
        {"type": "CHOCH", "ts_ms": ts - 120_000, "details_json": {}},
        {"type": "CHOCH", "ts_ms": ts - 60_000, "details_json": {}},
    ]
    ctx = _base_ctx()
    ctx["structure_state"] = {"trend_dir": "UP", "compression_flag": False, "breakout_box_json": {}}
    ctx["structure_events"] = events
    ctx["primary_feature"] = {"range_score": 50.0, "atrp_14": 0.08}
    ctx["features_by_tf"] = {"15m": {"trend_dir": 1}, "1H": {"trend_dir": 1}, "4H": {"trend_dir": 1}}
    inp = RegimeEngineInputs(**ctx)
    r = classify_regime(inp)
    assert r.market_regime == "chop"
    assert r.regime_state == "mean_reverting"
    assert r.regime_substate == "mean_reverting_choch_churn"


def test_identical_inputs_bit_stable() -> None:
    d = _base_ctx()
    d["primary_feature"] = {"range_score": 30.0, "atrp_14": 0.12}
    a = classify_regime(RegimeEngineInputs(**d))
    b = classify_regime(RegimeEngineInputs(**d))
    assert a.regime_snapshot == b.regime_snapshot
