"""Gruppierte Signal-Sicht (`signal_view`) und Erklärungsebenen (`explanation_layers`).

Semantik:
- Persistente Erklärung (app.signal_explanations): menschlich, versionierbar, unabhängig von Live-LLM.
- Deterministische Engine (app.signals_v1.reasons_json): maschineller Audit-Pfad; autoritativ für
  „was die Engine gespeichert hat“.
- Live-LLM-Advisory: separater BFF-/Operator-Request; ersetzt weder Persistenz noch reasons_json.
"""

from __future__ import annotations

from typing import Any, Mapping

SIGNAL_API_CONTRACT_VERSION = "1.2.0"


def _pick(d: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: d.get(k) for k in keys}


def reasons_json_shape_summary(reasons_json: Any) -> dict[str, Any]:
    if reasons_json is None:
        return {"kind": "null"}
    if isinstance(reasons_json, dict):
        keys = sorted(str(k) for k in reasons_json.keys())
        return {"kind": "object", "top_level_keys": keys[:48], "truncated": len(keys) > 48}
    if isinstance(reasons_json, list):
        return {"kind": "array", "length": len(reasons_json)}
    return {"kind": "scalar"}


_LIST_IDENTITY = (
    "signal_id",
    "symbol",
    "timeframe",
    "direction",
    "analysis_ts_ms",
    "created_ts",
    "canonical_instrument_id",
    "market_family",
)

_LIST_DECISION = (
    "signal_class",
    "decision_state",
    "trade_action",
    "meta_decision_action",
    "meta_decision_kernel_version",
)

_LIST_STRATEGY = (
    "strategy_name",
    "playbook_id",
    "playbook_family",
    "playbook_decision_mode",
    "specialist_router_id",
    "router_selected_playbook_id",
    "router_operator_gate_required",
    "exit_family_effective_primary",
    "exit_family_primary_ensemble",
)

_LIST_REGIME = (
    "market_regime",
    "regime_bias",
    "regime_confidence_0_1",
    "regime_state",
    "regime_substate",
    "regime_transition_state",
    "meta_trade_lane",
)

_LIST_SCORES = (
    "signal_strength_0_100",
    "probability_0_1",
    "take_trade_prob",
    "expected_return_bps",
    "expected_mae_bps",
    "expected_mfe_bps",
    "model_uncertainty_0_1",
    "uncertainty_effective_for_leverage_0_1",
    "model_ood_alert",
    "take_trade_model_version",
    "take_trade_model_run_id",
    "take_trade_calibration_method",
    "decision_confidence_0_1",
    "decision_policy_version",
    "allowed_leverage",
    "recommended_leverage",
    "leverage_policy_version",
    "leverage_cap_reasons_json",
)

_LIST_RISK_STOPS = (
    "stop_distance_pct",
    "stop_budget_max_pct_allowed",
    "stop_min_executable_pct",
    "stop_fragility_0_1",
    "stop_executability_0_1",
    "stop_quality_0_1",
    "stop_to_spread_ratio",
    "stop_budget_policy_version",
)

_LIST_GOVERNOR = (
    "live_execution_block_reasons_json",
    "governor_universal_hard_block_reasons_json",
    "live_execution_clear_for_real_money",
)

_LIST_EXECUTION = (
    "latest_execution_id",
    "latest_execution_decision_action",
    "latest_execution_decision_reason",
    "latest_execution_runtime_mode",
    "latest_execution_requested_mode",
    "latest_execution_created_ts",
    "operator_release_exists",
    "operator_release_source",
    "operator_release_ts",
    "live_mirror_eligible",
    "shadow_live_match_ok",
    "shadow_live_hard_violations",
    "shadow_live_soft_violations",
    "telegram_alert_type",
    "telegram_delivery_state",
    "telegram_message_id",
    "telegram_sent_ts",
)

_DETAIL_INSTRUMENT = (
    "instrument_metadata_snapshot_id",
    "instrument_venue",
    "instrument_category_key",
    "instrument_metadata_source",
    "instrument_metadata_verified",
    "instrument_product_type",
    "instrument_margin_account_mode",
    "instrument_base_coin",
    "instrument_quote_coin",
    "instrument_settle_coin",
    "instrument_inventory_visible",
    "instrument_analytics_eligible",
    "instrument_paper_shadow_eligible",
    "instrument_live_execution_enabled",
    "instrument_execution_disabled",
    "instrument_supports_funding",
    "instrument_supports_open_interest",
    "instrument_supports_long_short",
    "instrument_supports_shorting",
    "instrument_supports_reduce_only",
    "instrument_supports_leverage",
)

_DETAIL_SCORING_EXTRA = (
    "target_projection_models_json",
    "shadow_divergence_0_1",
    "model_ood_score_0_1",
    "uncertainty_reasons_json",
    "ood_reasons_json",
    "abstention_reasons_json",
    "regime_reasons_json",
)

_DETAIL_PORTFOLIO = ("portfolio_risk_synthesis_json",)


def build_signal_view_list_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_version": SIGNAL_API_CONTRACT_VERSION,
        "identity": _pick(item, _LIST_IDENTITY),
        "decision_and_status": _pick(item, _LIST_DECISION),
        "strategy_and_routing": _pick(item, _LIST_STRATEGY),
        "regime": _pick(item, _LIST_REGIME),
        "scores_and_leverage": _pick(item, _LIST_SCORES),
        "risk_stops": _pick(item, _LIST_RISK_STOPS),
        "risk_governor": _pick(item, _LIST_GOVERNOR),
        "execution_and_alerts": _pick(item, _LIST_EXECUTION),
        "outcome": _pick(item, ("outcome_badge",)),
        "deterministic_engine": {
            "reasons_json_on_this_endpoint": False,
            "read_from": "GET /v1/signals/{signal_id} Feld reasons_json "
            "oder GET /v1/signals/{signal_id}/explain → explanation_layers.deterministic_engine",
        },
    }


def build_signal_view_detail(item: Mapping[str, Any]) -> dict[str, Any]:
    base = build_signal_view_list_item(item)
    base["decision_and_status"] = _pick(
        item,
        _LIST_DECISION
        + (
            "rejection_state",
            "rejection_reasons_json",
        ),
    )
    base["instrument_and_metadata"] = _pick(item, _DETAIL_INSTRUMENT)
    base["scoring_diagnostics"] = _pick(item, _DETAIL_SCORING_EXTRA)
    base["portfolio"] = _pick(item, _DETAIL_PORTFOLIO)
    rj = item.get("reasons_json")
    base["deterministic_engine"] = {
        "reasons_json_ref": "reasons_json",
        "shape": reasons_json_shape_summary(rj),
        "note_de": "Vollständige Engine-Struktur liegt im Top-Level-Feld reasons_json; "
        "dies ist nur eine kompakte Signatur für Listen/Diffs.",
        "note_en": "Full engine structure is in top-level reasons_json; this is a compact signature.",
    }
    return base


def build_explanation_layers(
    *,
    explain_short: Any,
    explain_long_md: Any,
    risk_warnings_json: Any,
    stop_explain_json: Any,
    targets_explain_json: Any,
    reasons_json: Any,
) -> dict[str, Any]:
    rw = risk_warnings_json if isinstance(risk_warnings_json, list) else []
    se = stop_explain_json if isinstance(stop_explain_json, dict) else {}
    te = targets_explain_json if isinstance(targets_explain_json, dict) else {}
    return {
        "persisted_narrative": {
            "source": "app.signal_explanations",
            "semantic": "human_persisted_copy",
            "explain_short": explain_short,
            "explain_long_md": explain_long_md,
            "risk_warnings_json": rw,
            "stop_explain_json": se,
            "targets_explain_json": te,
            "note_de": "Gespeicherte Texte/JSON der Erklärungstabelle; unabhängig von Live-LLM.",
            "note_en": "Persisted explanation copy; independent of live LLM.",
        },
        "deterministic_engine": {
            "source": "app.signals_v1.reasons_json",
            "semantic": "engine_audit_trail",
            "reasons_json": reasons_json,
            "shape": reasons_json_shape_summary(reasons_json),
            "note_de": "Identisch zum Top-Level-Feld reasons_json in dieser Antwort; autoritativ für "
            "die Engine-Persistenz.",
            "note_en": "Same as top-level reasons_json in this response; authoritative engine payload.",
        },
        "live_llm_advisory": {
            "source": "bff_or_operator_endpoint",
            "semantic": "advisory_overlay",
            "separate_request": True,
            "note_de": "Live-KI-Erklärungen laufen über eine eigene Anfrage (z. B. Operator-BFF). "
            "Sie widersprechen absichtlich nicht reasons_json oder der gespeicherten Erklärung, "
            "können aber anderen Fokus/Ton haben.",
            "note_en": "Live LLM explanations use a separate request; they do not replace "
            "reasons_json or persisted narrative but may use different focus/tone.",
        },
    }
