from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.models import ScoringContext
from signal_engine.service import run_scoring_pipeline


def test_pipeline_deterministic_twice(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP", "compression_flag": True},
        structure_events=[],
        primary_feature={
            "momentum_score": 58.0,
            "rsi_14": 52.0,
            "ret_1": 0.001,
            "impulse_body_ratio": 0.5,
            "vol_z_50": 0.3,
            "computed_ts_ms": 1_700_000_000_000,
            "atrp_14": 0.09,
        },
        features_by_tf={
            "1m": {"trend_dir": 1},
            "5m": {"trend_dir": 1},
            "15m": {"trend_dir": 1},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 0},
        },
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99000",
                    "price_high": "99100",
                },
                "reasons": [],
                "confidence": 50.0,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "102000",
                    "price_high": "103000",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    a = run_scoring_pipeline(ctx, signal_settings, prior_total=0, prior_avg=None)
    b = run_scoring_pipeline(ctx, signal_settings, prior_total=0, prior_avg=None)
    # Ohne Replay-Trace: signal_id zufaellig; Teilscores identisch
    assert a["db_row"]["structure_score_0_100"] == b["db_row"]["structure_score_0_100"]
    assert a["db_row"]["momentum_score_0_100"] == b["db_row"]["momentum_score_0_100"]
    assert (
        a["db_row"]["weighted_composite_score_0_100"]
        == b["db_row"]["weighted_composite_score_0_100"]
    )
    assert a["db_row"]["direction"] == b["db_row"]["direction"]
    assert a["db_row"]["market_regime"] == b["db_row"]["market_regime"]
    assert a["db_row"]["regime_bias"] == b["db_row"]["regime_bias"]
    assert a["db_row"]["take_trade_prob"] == b["db_row"]["take_trade_prob"] is None
    assert (
        a["db_row"]["expected_return_bps"] == b["db_row"]["expected_return_bps"] is None
    )
    assert a["db_row"]["expected_mae_bps"] == b["db_row"]["expected_mae_bps"] is None
    assert a["db_row"]["expected_mfe_bps"] == b["db_row"]["expected_mfe_bps"] is None
    assert (
        a["db_row"]["model_uncertainty_0_1"]
        == b["db_row"]["model_uncertainty_0_1"]
        is None
    )
    assert (
        a["db_row"]["decision_confidence_0_1"]
        == b["db_row"]["decision_confidence_0_1"]
        is None
    )
    assert a["db_row"]["allowed_leverage"] == b["db_row"]["allowed_leverage"] is None
    assert (
        a["db_row"]["recommended_leverage"]
        == b["db_row"]["recommended_leverage"]
        is None
    )
    assert (
        a["db_row"]["leverage_cap_reasons_json"]
        == b["db_row"]["leverage_cap_reasons_json"]
        == []
    )
    keys = (
        "bullish_factors",
        "bearish_factors",
        "market_regime",
        "regime_bias",
        "regime_notes",
        "structural_notes",
        "momentum_notes",
        "timeframe_notes",
        "risk_notes",
        "news_notes",
        "history_notes",
        "decisive_factors",
    )
    for k in keys:
        assert k in a["db_row"]["reasons_json"]
    assert a["db_row"]["market_regime"] == "compression"
    assert a["db_row"]["regime_bias"] == "long"
    assert isinstance(a["db_row"]["regime_reasons_json"], list)
    assert a["db_row"]["playbook_decision_mode"] in {"selected", "playbookless"}
    assert (
        a["db_row"]["source_snapshot_json"]["regime_snapshot"]["market_regime"]
        == "compression"
    )
    assert a["db_row"]["source_snapshot_json"]["take_trade_model"] is None
    assert a["db_row"]["source_snapshot_json"]["target_projection_summary"] is None
    assert a["db_row"]["source_snapshot_json"]["uncertainty_assessment"] is None
    assert a["db_row"]["source_snapshot_json"]["hybrid_decision"] is None
    assert a["event_payload"]["market_regime"] == "compression"
    assert a["event_payload"]["playbook_decision_mode"] == a["db_row"]["playbook_decision_mode"]
    assert a["event_payload"]["take_trade_prob"] is None
    assert a["event_payload"]["expected_return_bps"] is None
    assert a["event_payload"]["trade_action"] == a["db_row"]["trade_action"]
    cc = a["db_row"]["source_snapshot_json"]["correlation_chain"]
    assert cc["schema"] == "correlation-v1"
    assert cc["signal_id"] == a["db_row"]["signal_id"]


def test_pipeline_stable_signal_id_with_replay_trace(signal_settings) -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1_700_000_000_000,
        structure_state={"trend_dir": "UP", "compression_flag": True},
        structure_events=[],
        primary_feature={
            "momentum_score": 58.0,
            "rsi_14": 52.0,
            "ret_1": 0.001,
            "impulse_body_ratio": 0.5,
            "vol_z_50": 0.3,
            "computed_ts_ms": 1_700_000_000_000,
            "atrp_14": 0.09,
        },
        features_by_tf={
            "1m": {"trend_dir": 1},
            "5m": {"trend_dir": 1},
            "15m": {"trend_dir": 1},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 0},
        },
        drawings=[
            {
                "drawing_id": "s1",
                "type": "stop_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "99000",
                    "price_high": "99100",
                },
                "reasons": [],
                "confidence": 50.0,
            },
            {
                "drawing_id": "t1",
                "type": "target_zone",
                "geometry": {
                    "kind": "horizontal_zone",
                    "price_low": "102000",
                    "price_high": "103000",
                },
                "reasons": [],
                "confidence": 50.0,
            },
        ],
        news_row=None,
        last_close=100_000.0,
    )
    trace = {
        "source": "learning_engine.replay",
        "session_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "candle_close_event_id": "ccc",
        "structure_updated_event_id": "sss",
    }
    a = run_scoring_pipeline(
        ctx,
        signal_settings,
        prior_total=0,
        prior_avg=None,
        causal_trace=trace,
        upstream_event_id="drawing-upstream-1",
    )
    b = run_scoring_pipeline(
        ctx,
        signal_settings,
        prior_total=0,
        prior_avg=None,
        causal_trace=trace,
        upstream_event_id="drawing-upstream-1",
    )
    assert a["db_row"]["signal_id"] == b["db_row"]["signal_id"]
    assert a["db_row"]["source_snapshot_json"]["correlation_chain"]["replay_session_id"] == (
        "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    )
