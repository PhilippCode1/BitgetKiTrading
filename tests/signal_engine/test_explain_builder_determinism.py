from __future__ import annotations

from uuid import UUID

from signal_engine.explain.builder import build_explanation_bundle
from signal_engine.explain.schemas import ExplainInput


def _minimal_signal_row(signal_id: str) -> dict:
    return {
        "signal_id": signal_id,
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "analysis_ts_ms": 1_700_000_000_000,
        "direction": "long",
        "signal_strength_0_100": 62,
        "probability_0_1": 0.58,
        "signal_class": "kern",
        "structure_score_0_100": 55,
        "momentum_score_0_100": 50,
        "multi_timeframe_score_0_100": 48,
        "news_score_0_100": 50,
        "risk_score_0_100": 45,
        "history_score_0_100": 50,
        "weighted_composite_score_0_100": 52,
        "rejection_state": False,
        "rejection_reasons_json": [],
        "decision_state": "accepted",
        "reasons_json": {
            "structural_notes": ["n1"],
            "momentum_notes": [],
            "timeframe_notes": ["t1"],
            "risk_notes": [],
            "playbook": {
                "playbook_id": "trend_continuation_core",
                "playbook_family": "trend_continuation",
                "playbook_decision_mode": "selected",
                "benchmark_rule_ids": ["trend_continuation_vs_pullback_same_regime"],
            },
        },
        "playbook_id": "trend_continuation_core",
        "playbook_family": "trend_continuation",
        "playbook_decision_mode": "selected",
        "playbook_registry_version": "1.1",
        "supporting_drawing_ids_json": [],
        "supporting_structure_event_ids_json": [],
        "stop_zone_id": None,
        "target_zone_ids_json": [],
        "reward_risk_ratio": 1.5,
        "stop_trigger_type": "mark_price",
    }


def test_build_explanation_bundle_deterministic(signal_settings) -> None:
    sid = str(UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"))
    inp = ExplainInput(
        signal_row=_minimal_signal_row(sid),
        structure_state={"trend_dir": "UP", "compression_flag": False},
        structure_events=[],
        primary_feature={
            "trend_dir": 1,
            "rsi_14": 52.0,
            "ret_1": 0.001,
            "computed_ts_ms": 1_700_000_000_000,
            "atr_14": 100.0,
        },
        features_by_tf={
            "1m": {"trend_dir": 1},
            "5m": {"trend_dir": 1},
            "15m": {"trend_dir": 0},
            "1H": {"trend_dir": 1},
            "4H": {"trend_dir": 1},
        },
        drawings=[
            {
                "drawing_id": "11111111-1111-1111-1111-111111111111",
                "type": "stop_zone",
                "geometry": {"price_low": "90000", "price_high": "90100"},
            },
            {
                "drawing_id": "22222222-2222-2222-2222-222222222222",
                "type": "target_zone",
                "geometry": {"price_low": "91000", "price_high": "91100"},
            },
        ],
        news_row=None,
        last_close=90_050.0,
    )
    a = build_explanation_bundle(inp, signal_settings)
    b = build_explanation_bundle(inp, signal_settings)
    assert a == b
    assert a["explain_short"] == b["explain_short"]
    assert a["explain_long_md"] == b["explain_long_md"]
    assert a["explain_long_json"] == b["explain_long_json"]
    assert "regime_context" in a["explain_long_json"]["sections"]
    assert "uncertainty_breakdown" in a["explain_long_json"]["sections"]
    assert "playbook_context" in a["explain_long_json"]["sections"]
