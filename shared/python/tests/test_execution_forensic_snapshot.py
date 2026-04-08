from __future__ import annotations

from shared_py.observability.execution_forensic import (
    build_live_broker_forensic_snapshot,
    redact_nested_mapping,
)


def test_redact_nested_mapping_strips_nested_secrets_and_pii() -> None:
    raw = {
        "accessToken": "secret",
        "telegram_chat_id": 123,
        "nested": {
            "system_prompt": "hidden",
            "client_secret": "hidden",
            "ok": 1,
        },
    }
    out = redact_nested_mapping(raw, max_depth=4)
    assert "accessToken" not in out
    assert "telegram_chat_id" not in out
    assert "system_prompt" not in out["nested"]
    assert "client_secret" not in out["nested"]
    assert out["nested"]["ok"] == 1


def test_build_live_broker_forensic_snapshot_includes_specialists_and_stop_budget() -> None:
    signal_payload = {
        "trade_action": "do_not_trade",
        "decision_state": "downgraded",
        "meta_trade_lane": "candidate_for_live",
        "playbook_id": "pb_trend",
        "playbook_family": "trend",
        "market_family": "futures",
        "regime_state": "trend",
        "stop_fragility_0_1": 0.81,
        "stop_executability_0_1": 0.33,
        "stop_distance_pct": 0.004,
        "stop_budget_max_pct_allowed": 0.003,
        "stop_min_executable_pct": 0.002,
        "stop_to_spread_ratio": 1.2,
        "stop_quality_0_1": 0.42,
        "model_uncertainty_0_1": 0.6,
        "abstention_reasons_json": ["uncertainty_high"],
        "rejection_reasons_json": ["stop_budget_blocked"],
        "leverage_cap_reasons_json": ["stop_budget_cap"],
        "live_execution_block_reasons_json": ["portfolio_live_execution_policy"],
        "governor_universal_hard_block_reasons_json": ["exchange_health"],
        "instrument_metadata": {
            "metadata_source": "/api/v2/mix/market/contracts",
            "metadata_verified": True,
            "product_type": "USDT-FUTURES",
            "margin_account_mode": "crossed",
            "supports_leverage": True,
            "supports_reduce_only": True,
            "supports_long_short": True,
        },
        "reasons_json": {
            "stop_budget_assessment": {
                "outcome": "blocked",
                "gate_reasons_json": ["stop_zone_not_protective"],
                "leverage_before": 12,
                "leverage_after": 7,
            },
            "specialists": {
                "base_model": {
                    "specialist_id": "base",
                    "proposal": {"proposed_trade_action": "allow_trade", "confidence_0_1": 0.7},
                },
                "playbook_specialist": {
                    "specialist_id": "playbook:pb_trend",
                    "proposal": {"proposed_trade_action": "do_not_trade", "reasons": ["anti_pattern"]},
                },
                "adversary_check": {
                    "dissent_score_0_1": 0.51,
                    "hard_veto_recommended": True,
                    "reasons": ["adversary_regime_conflict"],
                },
                "router_arbitration": {
                    "router_id": "deterministic_specialist_router_v1",
                    "pre_adversary_trade_action": "allow_trade",
                    "selected_trade_action": "do_not_trade",
                    "selected_playbook_id": "pb_trend",
                    "selected_meta_trade_lane": "candidate_for_live",
                    "operator_gate_required": True,
                    "reasons": ["ensemble_disagreement"],
                },
            },
            "decision_control_flow": {
                "pipeline_version": "se-end-decision-v4",
                "no_trade_path": {
                    "policy_text_de": "No-trade bleibt korrekt.",
                    "phase_block_drivers": ["stop_budget", "adversary_veto"],
                    "top_abstention_reasons": ["uncertainty_high"],
                },
                "end_decision_binding": {
                    "exit_family_primary": "scale_out",
                    "exit_family_effective_primary": "runner",
                },
                "final_summary": {"trade_action": "do_not_trade"},
            },
        },
    }
    snapshot = build_live_broker_forensic_snapshot(
        signal_payload=signal_payload,
        risk_decision={"trade_action": "do_not_trade", "decision_reason": "shared_risk_blocked"},
        shadow_live_report={"shadow_live_divergence": {"match_ok": False, "hard_violations": ["shadow_gap"]}},
        trace={"catalog_instrument": {"market_family": "futures", "symbol": "BTCUSDT", "product_type": "USDT-FUTURES"}},
    )
    assert snapshot["schema_version"] == 2
    assert snapshot["router"]["router_id"] == "deterministic_specialist_router_v1"
    assert snapshot["specialists"]["playbook_specialist"]["specialist_id"] == "playbook:pb_trend"
    assert snapshot["stop_budget"]["outcome"] == "blocked"
    assert snapshot["decision_control_flow"]["no_trade_path"]["phase_block_drivers_head"] == [
        "stop_budget",
        "adversary_veto",
    ]
    assert snapshot["instrument_metadata_min"]["metadata_verified"] is True
    assert snapshot["shadow_live"]["match_ok"] is False
