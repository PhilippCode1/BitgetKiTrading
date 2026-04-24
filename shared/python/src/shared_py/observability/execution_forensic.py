"""
Forensik-Snapshots fuer Live-Execution (keine Secrets, keine LLM-Rohprompts).

Apex-Audit-Ledger (entscheidungs-Hash-Kette, Signatur): Begruendungspaket
``build_ledger_decision_package`` bzw. :mod:`shared_py.observability.ledger_decision_package`.

Golden Record je Trade (Signal→KI→Risiko→Fill, Hash-Kette): :mod:`shared_py.observability.trade_lifecycle_audit`.
"""

from __future__ import annotations

import copy
from typing import Any

_FORENSIC_DENYLIST_KEYS = frozenset(
    {
        "password",
        "secret",
        "api_key",
        "api_secret",
        "passphrase",
        "token",
        "authorization",
        "private_key",
        "credential",
        "bearer",
        "x-internal-service-key",
    }
)

_FORENSIC_DENYLIST_SUBSTRINGS = (
    "token",
    "secret",
    "passphrase",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "cookie",
    "session",
    "prompt",
    "messages",
    "completion",
    "raw_llm",
)

_FORENSIC_PII_SUBSTRINGS = (
    "chat_id",
    "user_id",
    "username",
    "first_name",
    "last_name",
    "full_name",
    "phone",
    "email",
)

# LLM-/Chat-Felder nicht in operative Journale spiegeln
_LLM_BLOCK_PREFIXES = ("prompt", "messages", "completion", "raw_llm")


def _is_blocked_key(key: str) -> bool:
    lk = key.lower().strip()
    if lk in _FORENSIC_DENYLIST_KEYS:
        return True
    if any(part in lk for part in _FORENSIC_DENYLIST_SUBSTRINGS):
        return True
    if any(part in lk for part in _FORENSIC_PII_SUBSTRINGS):
        return True
    return any(lk.startswith(p) for p in _LLM_BLOCK_PREFIXES)


def redact_nested_mapping(obj: Any, *, max_depth: int = 4) -> Any:
    """Entfernt verschachtelte Schluessel, die Secrets oder Roh-LLM-Inhalte tragen koennten."""

    def _walk(node: Any, depth: int) -> Any:
        if depth > max_depth:
            return "[truncated_depth]"
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for k, v in node.items():
                sk = str(k)
                if _is_blocked_key(sk):
                    continue
                out[sk] = _walk(v, depth + 1)
            return out
        if isinstance(node, list):
            return [_walk(x, depth + 1) for x in node[:50]]
        return node

    return _walk(obj, 0)


def _trunc_list(val: Any, *, max_items: int = 14, max_str: int = 200) -> list[str]:
    if not isinstance(val, list):
        return []
    out: list[str] = []
    for x in val[:max_items]:
        s = x if isinstance(x, str) else str(x)
        s = s.strip()
        if len(s) > max_str:
            s = s[: max_str - 3] + "..."
        if s:
            out.append(s)
    return out


def _proposal_summary(block: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(block, dict):
        return {}
    proposal = block.get("proposal")
    proposal = proposal if isinstance(proposal, dict) else {}
    return {
        "specialist_id": block.get("specialist_id"),
        "proposed_trade_action": proposal.get("proposed_trade_action"),
        "confidence_0_1": proposal.get("confidence_0_1"),
        "direction": proposal.get("direction"),
        "no_trade_probability_0_1": proposal.get("no_trade_probability_0_1"),
        "expected_edge_bps": proposal.get("expected_edge_bps"),
        "expected_mae_bps": proposal.get("expected_mae_bps"),
        "expected_mfe_bps": proposal.get("expected_mfe_bps"),
        "exit_family_primary": proposal.get("exit_family_primary"),
        "stop_budget_hint_0_1": proposal.get("stop_budget_hint_0_1"),
        "uncertainty_0_1": proposal.get("uncertainty_0_1"),
        "reasons_head": _trunc_list(proposal.get("reasons")),
    }


def _stop_budget_summary(payload: dict[str, Any], reasons_json: dict[str, Any]) -> dict[str, Any]:
    sba = reasons_json.get("stop_budget_assessment")
    sba = sba if isinstance(sba, dict) else {}
    return {
        "outcome": sba.get("outcome") or payload.get("stop_budget_outcome"),
        "stop_distance_pct": payload.get("stop_distance_pct"),
        "stop_budget_max_pct_allowed": payload.get("stop_budget_max_pct_allowed"),
        "stop_min_executable_pct": payload.get("stop_min_executable_pct"),
        "stop_to_spread_ratio": payload.get("stop_to_spread_ratio"),
        "stop_quality_0_1": payload.get("stop_quality_0_1"),
        "stop_executability_0_1": payload.get("stop_executability_0_1"),
        "stop_fragility_0_1": payload.get("stop_fragility_0_1"),
        "leverage_before": sba.get("leverage_before"),
        "leverage_after": sba.get("leverage_after"),
        "liquidation_proximity_stress_0_1": sba.get("liquidation_proximity_stress_0_1"),
        "gate_reasons_head": _trunc_list(sba.get("gate_reasons_json")),
    }


def _instrument_metadata_min(payload: dict[str, Any]) -> dict[str, Any]:
    inst = payload.get("instrument")
    inst = inst if isinstance(inst, dict) else {}
    meta = payload.get("instrument_metadata")
    meta = meta if isinstance(meta, dict) else {}
    return {
        "canonical_instrument_id": payload.get("canonical_instrument_id"),
        "market_family": payload.get("market_family") or inst.get("market_family") or meta.get("market_family"),
        "symbol": payload.get("symbol") or inst.get("symbol"),
        "product_type": meta.get("product_type") or inst.get("product_type"),
        "margin_account_mode": meta.get("margin_account_mode") or inst.get("margin_account_mode"),
        "metadata_source": meta.get("metadata_source"),
        "metadata_verified": meta.get("metadata_verified"),
        "inventory_visible": meta.get("inventory_visible") or inst.get("inventory_visible"),
        "analytics_eligible": meta.get("analytics_eligible") or inst.get("analytics_eligible"),
        "paper_shadow_eligible": meta.get("paper_shadow_eligible")
        or inst.get("paper_shadow_eligible"),
        "live_execution_enabled": meta.get("live_execution_enabled")
        or inst.get("live_execution_enabled"),
        "execution_disabled": meta.get("execution_disabled") or inst.get("execution_disabled"),
        "supports_long_short": meta.get("supports_long_short"),
        "supports_shorting": meta.get("supports_shorting"),
        "supports_reduce_only": meta.get("supports_reduce_only"),
        "supports_leverage": meta.get("supports_leverage"),
    }


def _decision_control_flow_summary(reasons_json: dict[str, Any]) -> dict[str, Any]:
    dcf = reasons_json.get("decision_control_flow")
    dcf = dcf if isinstance(dcf, dict) else {}
    nt = dcf.get("no_trade_path")
    nt = nt if isinstance(nt, dict) else {}
    final_summary = dcf.get("final_summary")
    final_summary = final_summary if isinstance(final_summary, dict) else {}
    return {
        "pipeline_version": dcf.get("pipeline_version"),
        "no_trade_path": {
            "policy_text_de": nt.get("policy_text_de"),
            "phase_block_drivers_head": _trunc_list(nt.get("phase_block_drivers")),
            "abstention_reasons_head": _trunc_list(nt.get("top_abstention_reasons")),
        },
        "final_summary": redact_nested_mapping(final_summary, max_depth=3),
    }


def _risk_engine_summary(risk: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(risk, dict):
        return {}
    metrics = risk.get("metrics")
    m = metrics if isinstance(metrics, dict) else {}
    return {
        "trade_action": risk.get("trade_action"),
        "decision_reason": str(risk.get("decision_reason") or risk.get("primary_reason") or "")[:240],
        "allowed_leverage": m.get("allowed_leverage"),
        "recommended_leverage": m.get("recommended_leverage"),
    }


def _shadow_summary(shadow: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(shadow, dict):
        return {}
    div = shadow.get("shadow_live_divergence") if isinstance(shadow.get("shadow_live_divergence"), dict) else shadow
    return {
        "match_ok": div.get("match_ok"),
        "hard_violation_count": len(div.get("hard_violations") or [])
        if isinstance(div.get("hard_violations"), list)
        else None,
        "soft_violation_count": len(div.get("soft_violations") or [])
        if isinstance(div.get("soft_violations"), list)
        else None,
    }


def build_live_broker_forensic_snapshot(
    *,
    signal_payload: dict[str, Any] | None,
    risk_decision: dict[str, Any] | None,
    shadow_live_report: dict[str, Any] | None,
    trace: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Kompaktes, auditierbares Bild fuer live.execution_journal (phase execution_decision).
    """
    p = copy.deepcopy(signal_payload) if isinstance(signal_payload, dict) else {}
    p = redact_nested_mapping(p, max_depth=5)
    if not isinstance(p, dict):
        p = {}

    reasons_json = p.get("reasons_json")
    rj = reasons_json if isinstance(reasons_json, dict) else {}
    specialists = rj.get("specialists") if isinstance(rj.get("specialists"), dict) else {}
    router = specialists.get("router_arbitration") if isinstance(specialists.get("router_arbitration"), dict) else {}
    dcf = rj.get("decision_control_flow") if isinstance(rj.get("decision_control_flow"), dict) else {}
    edb = dcf.get("end_decision_binding") if isinstance(dcf.get("end_decision_binding"), dict) else {}

    abst = _trunc_list(p.get("abstention_reasons_json"))
    lev_caps = _trunc_list(p.get("leverage_cap_reasons_json"))
    router_reasons = _trunc_list(router.get("reasons"))
    rejection_head = _trunc_list(p.get("rejection_reasons_json"))
    live_blocks = _trunc_list(p.get("live_execution_block_reasons_json"))
    universal_blocks = _trunc_list(p.get("governor_universal_hard_block_reasons_json"))

    tr = trace if isinstance(trace, dict) else {}
    catalog = tr.get("catalog_instrument")
    catalog_min = None
    if isinstance(catalog, dict):
        catalog_min = {
            "market_family": catalog.get("market_family"),
            "symbol": catalog.get("symbol"),
            "product_type": catalog.get("product_type"),
        }

    return {
        "schema_version": 2,
        "signal": {
            "trade_action": p.get("trade_action"),
            "meta_decision_action": p.get("meta_decision_action"),
            "meta_decision_kernel_version": p.get("meta_decision_kernel_version"),
            "decision_state": p.get("decision_state"),
            "meta_trade_lane": p.get("meta_trade_lane"),
            "playbook_id": p.get("playbook_id"),
            "playbook_family": p.get("playbook_family"),
            "market_family": p.get("market_family"),
            "market_regime": p.get("market_regime"),
            "regime_state": p.get("regime_state"),
            "stop_fragility_0_1": p.get("stop_fragility_0_1"),
            "stop_executability_0_1": p.get("stop_executability_0_1"),
            "stop_distance_pct": p.get("stop_distance_pct"),
            "stop_budget_max_pct_allowed": p.get("stop_budget_max_pct_allowed"),
            "model_uncertainty_0_1": p.get("model_uncertainty_0_1"),
            "abstention_reasons_head": abst,
            "leverage_cap_reasons_head": lev_caps,
            "rejection_reasons_head": rejection_head,
            "live_execution_block_reasons_head": live_blocks,
            "governor_universal_hard_block_reasons_head": universal_blocks,
        },
        "instrument_metadata_min": _instrument_metadata_min(p),
        "specialists": {
            "base_model": _proposal_summary(
                specialists.get("base_model") if isinstance(specialists.get("base_model"), dict) else None
            ),
            "family_specialist": _proposal_summary(
                specialists.get("family_specialist")
                if isinstance(specialists.get("family_specialist"), dict)
                else None
            ),
            "regime_specialist": _proposal_summary(
                specialists.get("regime_specialist")
                if isinstance(specialists.get("regime_specialist"), dict)
                else None
            ),
            "playbook_specialist": _proposal_summary(
                specialists.get("playbook_specialist")
                if isinstance(specialists.get("playbook_specialist"), dict)
                else None
            ),
            "product_margin_specialist": _proposal_summary(
                specialists.get("product_margin_specialist")
                if isinstance(specialists.get("product_margin_specialist"), dict)
                else None
            ),
            "liquidity_vol_cluster_specialist": _proposal_summary(
                specialists.get("liquidity_vol_cluster_specialist")
                if isinstance(specialists.get("liquidity_vol_cluster_specialist"), dict)
                else None
            ),
            "symbol_specialist": _proposal_summary(
                specialists.get("symbol_specialist")
                if isinstance(specialists.get("symbol_specialist"), dict)
                else None
            ),
            "ensemble_hierarchy_head": _trunc_list(
                [
                    str(x.get("role")) + ":" + str(x.get("specialist_id"))
                    for x in (specialists.get("ensemble_hierarchy") or [])
                    if isinstance(x, dict)
                ][:10]
            ),
            "adversary_check": {
                "dissent_score_0_1": (
                    (specialists.get("adversary_check") or {}).get("dissent_score_0_1")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "hard_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("hard_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "directional_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("directional_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "tri_way_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("tri_way_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "edge_dispersion_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("edge_dispersion_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "regime_mismatch_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("regime_mismatch_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "regime_bias_conflict_veto_recommended": (
                    (specialists.get("adversary_check") or {}).get("regime_bias_conflict_veto_recommended")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else None
                ),
                "reasons_head": _trunc_list(
                    (specialists.get("adversary_check") or {}).get("reasons")
                    if isinstance(specialists.get("adversary_check"), dict)
                    else []
                ),
            },
        },
        "router": {
            "router_id": router.get("router_id"),
            "pre_adversary_trade_action": router.get("pre_adversary_trade_action"),
            "selected_trade_action": router.get("selected_trade_action"),
            "selected_playbook_id": router.get("selected_playbook_id"),
            "selected_meta_trade_lane": router.get("selected_meta_trade_lane"),
            "ensemble_confidence_multiplier_0_1": router.get("ensemble_confidence_multiplier_0_1"),
            "operator_gate_required": router.get("operator_gate_required"),
            "reasons_head": router_reasons,
        },
        "exit_binding": {
            "exit_family_primary": edb.get("exit_family_primary"),
            "exit_family_effective_primary": edb.get("exit_family_effective_primary"),
        },
        "stop_budget": _stop_budget_summary(p, rj),
        "decision_control_flow": _decision_control_flow_summary(rj),
        "risk_engine": _risk_engine_summary(risk_decision if isinstance(risk_decision, dict) else None),
        "shadow_live": _shadow_summary(
            shadow_live_report if isinstance(shadow_live_report, dict) else None
        ),
        "catalog_instrument_min": catalog_min,
    }


def build_forensic_timeline_phases(events: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Ordnet flache Timeline-Ereignisse (Gateway-Forensik) in Phasen fuer Runbooks/Dashboards.

    ``timeline_sorted`` bleibt die kanonische sortierte Liste; ``phases`` verweist nur per Index.
    """
    phases: dict[str, list[int]] = {
        "inputs": [],
        "specialists_and_decision_binding": [],
        "execution_decision": [],
        "operator_release": [],
        "orders_fills_journal": [],
        "exit": [],
        "post_trade_review": [],
        "notifications": [],
        "governance_audit": [],
    }
    for i, e in enumerate(events):
        k = str(e.get("kind") or "")
        if k == "signal_context":
            phases["inputs"].append(i)
        elif k == "specialist_path_marker":
            phases["specialists_and_decision_binding"].append(i)
        elif k == "execution_decision":
            phases["execution_decision"].append(i)
        elif k == "operator_release":
            phases["operator_release"].append(i)
        elif k in ("order", "fill") or k.startswith("journal:"):
            phases["orders_fills_journal"].append(i)
        elif k == "exit_plan":
            phases["exit"].append(i)
        elif k in ("trade_review", "learning_e2e_record"):
            phases["post_trade_review"].append(i)
        elif k.startswith("telegram_"):
            phases["notifications"].append(i)
        elif k == "gateway_audit":
            phases["governance_audit"].append(i)
    return {
        "schema_version": "forensic-phases-v1",
        "phase_ids_de": {
            "inputs": "Eingaben & Signal-Kontext",
            "specialists_and_decision_binding": "Spezialisten & Decision-Flow (siehe signal_path_summary)",
            "execution_decision": "Live-Broker Execution-Entscheidung",
            "operator_release": "Operator-Freigabe / Release",
            "orders_fills_journal": "Orders, Fills, Journalphasen",
            "exit": "Exit-Plan",
            "post_trade_review": "Post-Trade / Learning-E2E",
            "notifications": "Benachrichtigungen (Telegram/Outbox)",
            "governance_audit": "Gateway- & Governance-Audit",
        },
        "indices_by_phase": phases,
    }


def redact_operator_journal_details(details: dict[str, Any] | None) -> dict[str, Any]:
    """Operator-Release-Details: keine freien Textbloecke mit Tokens."""
    if not isinstance(details, dict):
        return {}
    return redact_nested_mapping(details, max_depth=4)


# Audit-Ledger: fachliche Fingerabdruecke (Signal / LLM+Konsens / Risk)
from shared_py.observability.ledger_decision_package import (  # noqa: E402
    build_ledger_decision_package,
    content_sha256_hex,
)
