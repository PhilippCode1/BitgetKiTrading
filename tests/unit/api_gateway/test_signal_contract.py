from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
API_GATEWAY_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, API_GATEWAY_SRC):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

from api_gateway.signal_contract import (
    SIGNAL_API_CONTRACT_VERSION,
    build_explanation_layers,
    build_signal_view_detail,
    build_signal_view_list_item,
    reasons_json_shape_summary,
)


def test_reasons_json_shape_summary() -> None:
    assert reasons_json_shape_summary(None)["kind"] == "null"
    assert reasons_json_shape_summary({"a": 1})["kind"] == "object"
    assert reasons_json_shape_summary([1, 2]) == {"kind": "array", "length": 2}


def test_list_and_detail_views_stable_keys() -> None:
    flat = {
        "signal_id": "00000000-0000-0000-0000-000000000099",
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "analysis_ts_ms": 1,
        "created_ts": None,
        "canonical_instrument_id": None,
        "market_family": "usdt_futures",
        "signal_class": "gross",
        "decision_state": "accepted",
        "trade_action": "allow_trade",
        "meta_decision_action": None,
        "meta_decision_kernel_version": None,
        "strategy_name": "s",
        "playbook_id": "p1",
        "playbook_family": "trend",
        "playbook_decision_mode": "selected",
        "specialist_router_id": None,
        "router_selected_playbook_id": None,
        "router_operator_gate_required": None,
        "exit_family_effective_primary": None,
        "exit_family_primary_ensemble": None,
        "market_regime": "trend",
        "regime_bias": "long",
        "regime_confidence_0_1": 0.5,
        "regime_state": None,
        "regime_substate": None,
        "regime_transition_state": None,
        "meta_trade_lane": "paper_default",
        "signal_strength_0_100": 50.0,
        "probability_0_1": 0.5,
        "take_trade_prob": None,
        "expected_return_bps": None,
        "expected_mae_bps": None,
        "expected_mfe_bps": None,
        "model_uncertainty_0_1": None,
        "uncertainty_effective_for_leverage_0_1": None,
        "model_ood_alert": False,
        "take_trade_model_version": None,
        "take_trade_model_run_id": None,
        "take_trade_calibration_method": None,
        "decision_confidence_0_1": None,
        "decision_policy_version": None,
        "allowed_leverage": None,
        "recommended_leverage": None,
        "leverage_policy_version": None,
        "leverage_cap_reasons_json": [],
        "stop_distance_pct": None,
        "stop_budget_max_pct_allowed": None,
        "stop_min_executable_pct": None,
        "stop_fragility_0_1": None,
        "stop_executability_0_1": None,
        "stop_quality_0_1": None,
        "stop_to_spread_ratio": None,
        "stop_budget_policy_version": None,
        "live_execution_block_reasons_json": [],
        "governor_universal_hard_block_reasons_json": [],
        "live_execution_clear_for_real_money": True,
        "latest_execution_id": None,
        "latest_execution_decision_action": None,
        "latest_execution_decision_reason": None,
        "latest_execution_runtime_mode": None,
        "latest_execution_requested_mode": None,
        "latest_execution_created_ts": None,
        "operator_release_exists": False,
        "operator_release_source": None,
        "operator_release_ts": None,
        "live_mirror_eligible": None,
        "shadow_live_match_ok": None,
        "shadow_live_hard_violations": None,
        "shadow_live_soft_violations": None,
        "telegram_alert_type": None,
        "telegram_delivery_state": None,
        "telegram_message_id": None,
        "telegram_sent_ts": None,
        "outcome_badge": None,
    }
    lv = build_signal_view_list_item(flat)
    assert lv["contract_version"] == SIGNAL_API_CONTRACT_VERSION
    assert set(lv.keys()) >= {
        "identity",
        "decision_and_status",
        "strategy_and_routing",
        "regime",
        "scores_and_leverage",
        "risk_stops",
        "risk_governor",
        "execution_and_alerts",
        "outcome",
        "deterministic_engine",
    }
    detail_flat = {
        **flat,
        "rejection_state": False,
        "rejection_reasons_json": [],
        "instrument_metadata_snapshot_id": None,
        "instrument_venue": None,
        "instrument_category_key": None,
        "instrument_metadata_source": None,
        "instrument_metadata_verified": None,
        "instrument_product_type": None,
        "instrument_margin_account_mode": None,
        "instrument_base_coin": None,
        "instrument_quote_coin": None,
        "instrument_settle_coin": None,
        "instrument_inventory_visible": None,
        "instrument_analytics_eligible": None,
        "instrument_paper_shadow_eligible": None,
        "instrument_live_execution_enabled": None,
        "instrument_execution_disabled": None,
        "instrument_supports_funding": None,
        "instrument_supports_open_interest": None,
        "instrument_supports_long_short": None,
        "instrument_supports_shorting": None,
        "instrument_supports_reduce_only": None,
        "instrument_supports_leverage": None,
        "target_projection_models_json": [],
        "shadow_divergence_0_1": None,
        "model_ood_score_0_1": None,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": [],
        "regime_reasons_json": [],
        "portfolio_risk_synthesis_json": None,
        "reasons_json": {"k": "v"},
    }
    dv = build_signal_view_detail(detail_flat)
    assert dv["deterministic_engine"]["reasons_json_ref"] == "reasons_json"
    assert dv["deterministic_engine"]["shape"]["kind"] == "object"


def test_explanation_layers_parallels_top_level_reasons() -> None:
    layers = build_explanation_layers(
        explain_short="s",
        explain_long_md="m",
        risk_warnings_json=[],
        stop_explain_json={},
        targets_explain_json={},
        reasons_json={"x": 1},
    )
    assert layers["deterministic_engine"]["reasons_json"] == {"x": 1}
    assert layers["live_llm_advisory"]["separate_request"] is True
    assert "note_de" in layers["persisted_narrative"]


def test_fixture_sample_roundtrip_json() -> None:
    path = REPO_ROOT / "tests" / "fixtures" / "signal_api_contract_sample.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    lv = build_signal_view_list_item(raw["list_item_flat"])
    assert lv["identity"]["signal_id"] == raw["list_item_flat"]["signal_id"]
    dv = build_signal_view_detail(raw["detail_flat"])
    assert dv["portfolio"]["portfolio_risk_synthesis_json"] == {"stress": "low"}
