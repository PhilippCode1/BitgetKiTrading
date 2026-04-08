from __future__ import annotations

from shared_py.shadow_live_forensics import compute_shadow_live_divergence


def test_forensics_regime_and_trade_action_match() -> None:
    live = {
        "market_regime": "trend",
        "trade_action": "allow_trade",
        "meta_trade_lane": "shadow_only",
        "source_snapshot_json": {
            "feature_snapshot": {
                "primary_tf": {"orderbook_age_ms": 1000.0},
            },
            "hybrid_decision": {"risk_governor": {"hard_block_reasons_json": []}},
        },
    }
    shadow = dict(live)
    out = compute_shadow_live_divergence(live, shadow)
    assert out["regime_match"] is True
    assert out["trade_action_match"] is True
    assert out["blockers"] == []


def test_forensics_detects_blocker_on_trade_mismatch() -> None:
    live = {
        "market_regime": "trend",
        "trade_action": "allow_trade",
        "meta_trade_lane": "shadow_only",
        "take_trade_prob": 0.8,
        "source_snapshot_json": {
            "feature_snapshot": {"primary_tf": {"orderbook_age_ms": 1000.0}},
            "hybrid_decision": {"risk_governor": {"hard_block_reasons_json": []}},
        },
    }
    shadow = {
        "market_regime": "trend",
        "trade_action": "do_not_trade",
        "meta_trade_lane": "shadow_only",
        "take_trade_prob": 0.5,
        "source_snapshot_json": {
            "feature_snapshot": {"primary_tf": {"orderbook_age_ms": 8000.0}},
            "hybrid_decision": {"risk_governor": {"hard_block_reasons_json": []}},
        },
    }
    out = compute_shadow_live_divergence(live, shadow)
    assert "shadow_blocks_trade_live_would_allow" in out["blockers"]
    assert "large_feature_age_delta_ms" in out["warnings"]
