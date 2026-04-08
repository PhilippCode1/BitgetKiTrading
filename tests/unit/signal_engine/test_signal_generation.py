"""Unit: Signal-Pipeline / Scoring deterministisch und Struktur der DB-Row."""

from __future__ import annotations

import pytest
from signal_engine.models import ScoringContext
from signal_engine.service import run_scoring_pipeline


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()


def test_scoring_produces_expected_db_row_shape(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "DOWN", "compression_flag": False},
        structure_events=[],
        primary_feature={
            "momentum_score": 40.0,
            "rsi_14": 35.0,
            "ret_1": -0.002,
            "impulse_body_ratio": 0.4,
            "vol_z_50": 0.1,
            "computed_ts_ms": 1_700_000_000_000,
            "atrp_14": 0.05,
        },
        features_by_tf={
            "1m": {"trend_dir": -1},
            "5m": {"trend_dir": -1},
            "15m": {"trend_dir": 0},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 1},
        },
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    out = run_scoring_pipeline(ctx, signal_settings, prior_total=0, prior_avg=None)
    row = out["db_row"]
    for key in (
        "direction",
        "market_regime",
        "regime_bias",
        "regime_confidence_0_1",
        "regime_reasons_json",
        "signal_strength_0_100",
        "probability_0_1",
        "take_trade_prob",
        "take_trade_model_version",
        "take_trade_model_run_id",
        "take_trade_calibration_method",
        "expected_return_bps",
        "expected_mae_bps",
        "expected_mfe_bps",
        "target_projection_models_json",
        "model_uncertainty_0_1",
        "shadow_divergence_0_1",
        "model_ood_score_0_1",
        "model_ood_alert",
        "uncertainty_reasons_json",
        "ood_reasons_json",
        "abstention_reasons_json",
        "trade_action",
        "decision_confidence_0_1",
        "decision_policy_version",
        "allowed_leverage",
        "recommended_leverage",
        "leverage_policy_version",
        "leverage_cap_reasons_json",
        "signal_class",
        "decision_state",
        "structure_score_0_100",
        "momentum_score_0_100",
    ):
        assert key in row
    assert row["market_regime"] in {
        "trend",
        "chop",
        "compression",
        "breakout",
        "shock",
        "dislocation",
    }
    assert row["regime_bias"] in {"long", "short", "neutral"}
    assert row["direction"] in ("long", "short", "neutral")
    assert 0 <= float(row["signal_strength_0_100"]) <= 100
    assert 0 <= float(row["probability_0_1"]) <= 1
    assert row["take_trade_prob"] is None
    assert row["take_trade_model_version"] is None
    assert row["expected_return_bps"] is None
    assert row["expected_mae_bps"] is None
    assert row["expected_mfe_bps"] is None
    assert row["target_projection_models_json"] == []
    assert row["model_uncertainty_0_1"] is None
    assert row["model_ood_alert"] is False
    assert row["trade_action"] in {"allow_trade", "do_not_trade"}
    assert row["decision_confidence_0_1"] is None
    assert row["decision_policy_version"] is None
    assert row["allowed_leverage"] is None
    assert row["recommended_leverage"] is None
    assert row["leverage_policy_version"] is None
    assert row["leverage_cap_reasons_json"] == []
