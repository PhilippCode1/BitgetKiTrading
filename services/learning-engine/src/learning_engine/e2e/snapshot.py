"""
E2E-Lern-Snapshot aus app.signals_v1 — deterministisch, ohne LLM.

Enthaelt Spezialisten-Votes, Router, No-Trade-Gruende, Stop-Budget/Fragilitaet,
Exit-Familien-Hinweise, Shadow/Live-Divergenz und Modellversionen fuer spaetere
Spezialisten-Trainings und Governance.
"""

from __future__ import annotations

import json
from typing import Any

E2E_SNAPSHOT_VERSION = "e2e-snapshot-v1"
E2E_RECORD_SCHEMA_VERSION = "e2e-v1"


def _parse_jsonb(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return {}
    return {}


def _router_path(specialists: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(specialists, dict):
        return None
    r = specialists.get("router_arbitration")
    return r if isinstance(r, dict) else None


def build_e2e_snapshot_from_signal_row(signal_row: dict[str, Any]) -> dict[str, Any]:
    rj = _parse_jsonb(signal_row.get("reasons_json"))
    if not isinstance(rj, dict):
        rj = {}
    snap = _parse_jsonb(signal_row.get("source_snapshot_json"))
    if not isinstance(snap, dict):
        snap = {}

    specialists = rj.get("specialists")
    if not isinstance(specialists, dict):
        specialists = snap.get("specialists") if isinstance(snap.get("specialists"), dict) else {}

    hybrid = snap.get("hybrid_decision") if isinstance(snap.get("hybrid_decision"), dict) else {}
    rg = hybrid.get("risk_governor") if isinstance(hybrid.get("risk_governor"), dict) else {}

    sba = snap.get("stop_budget_assessment") if isinstance(snap.get("stop_budget_assessment"), dict) else {}

    det = rj.get("deterministic_gates") if isinstance(rj.get("deterministic_gates"), dict) else {}

    smc_sum = (
        rj.get("structured_market_context_summary")
        if isinstance(rj.get("structured_market_context_summary"), dict)
        else None
    )
    smc_full = (
        snap.get("structured_market_context") if isinstance(snap.get("structured_market_context"), dict) else None
    )

    dcf = rj.get("decision_control_flow") if isinstance(rj.get("decision_control_flow"), dict) else None

    inst = snap.get("instrument") if isinstance(snap.get("instrument"), dict) else {}
    iexec = snap.get("instrument_execution") if isinstance(snap.get("instrument_execution"), dict) else {}

    router = _router_path(specialists)
    exit_hint: dict[str, Any] = {}
    pb = specialists.get("playbook_specialist") if isinstance(specialists, dict) else None
    if isinstance(pb, dict):
        prop = pb.get("proposal") if isinstance(pb.get("proposal"), dict) else {}
        exit_hint = {
            "exit_family_primary": prop.get("exit_family_primary"),
            "exit_families_ranked": prop.get("exit_families_ranked"),
            "stop_budget_0_1": prop.get("stop_budget_0_1"),
        }

    shadow_div = None
    if isinstance(signal_row.get("shadow_divergence_0_1"), (int, float)):
        shadow_div = float(signal_row["shadow_divergence_0_1"])

    model_versions = {
        "scoring_model_version": signal_row.get("scoring_model_version"),
        "take_trade_model_version": signal_row.get("take_trade_model_version"),
        "take_trade_model_run_id": signal_row.get("take_trade_model_run_id"),
        "decision_policy_version": signal_row.get("decision_policy_version"),
        "regime_policy_version": signal_row.get("regime_policy_version"),
        "leverage_policy_version": signal_row.get("leverage_policy_version"),
        "unified_leverage_allocator_version": signal_row.get("unified_leverage_allocator_version"),
        "stop_budget_policy_version": sba.get("policy_version") if sba else None,
    }

    leverage_band = {
        "allowed_leverage": signal_row.get("allowed_leverage"),
        "recommended_leverage": signal_row.get("recommended_leverage"),
        "execution_leverage_cap": signal_row.get("execution_leverage_cap"),
        "mirror_leverage": signal_row.get("mirror_leverage"),
    }

    return {
        "snapshot_schema_version": E2E_SNAPSHOT_VERSION,
        "proposal_and_votes": {
            "specialists": specialists,
            "router_arbitration": router,
            "playbook_exit_hint": exit_hint,
        },
        "final_decision": {
            "trade_action": signal_row.get("trade_action"),
            "decision_state": signal_row.get("decision_state"),
            "meta_trade_lane": signal_row.get("meta_trade_lane"),
            "direction": signal_row.get("direction"),
            "signal_class": signal_row.get("signal_class"),
            "rejection_state": signal_row.get("rejection_state"),
            "rejection_reasons_json": signal_row.get("rejection_reasons_json"),
            "abstention_reasons_json": signal_row.get("abstention_reasons_json"),
        },
        "no_trade_and_gates": {
            "deterministic_gates": det,
            "risk_governor": {
                "hard_block_reasons_json": rg.get("hard_block_reasons_json"),
                "universal_hard_block_reasons_json": rg.get("universal_hard_block_reasons_json"),
                "live_execution_block_reasons_json": rg.get("live_execution_block_reasons_json"),
                "max_exposure_fraction_0_1": rg.get("max_exposure_fraction_0_1"),
            },
        },
        "stop_and_execution_quality": {
            "stop_budget_assessment": sba,
            "stop_distance_pct": signal_row.get("stop_distance_pct"),
            "stop_budget_max_pct_allowed": signal_row.get("stop_budget_max_pct_allowed"),
            "stop_min_executable_pct": signal_row.get("stop_min_executable_pct"),
            "stop_fragility_0_1": signal_row.get("stop_fragility_0_1"),
            "stop_executability_0_1": signal_row.get("stop_executability_0_1"),
            "stop_quality_0_1": signal_row.get("stop_quality_0_1"),
            "stop_to_spread_ratio": signal_row.get("stop_to_spread_ratio"),
        },
        "exit_and_targets": {
            "target_projection_models_json": signal_row.get("target_projection_models_json"),
            "expected_return_bps": signal_row.get("expected_return_bps"),
            "expected_mae_bps": signal_row.get("expected_mae_bps"),
            "expected_mfe_bps": signal_row.get("expected_mfe_bps"),
        },
        "market_context": {
            "structured_market_context_summary": smc_sum,
            "structured_market_context": smc_full,
            "market_regime": signal_row.get("market_regime"),
            "regime_state": signal_row.get("regime_state"),
            "regime_bias": signal_row.get("regime_bias"),
            "regime_confidence_0_1": signal_row.get("regime_confidence_0_1"),
        },
        "instrument": {
            "instrument": inst,
            "instrument_execution": iexec,
        },
        "shadow_live_divergence": {
            "shadow_divergence_0_1": shadow_div,
            "decision_control_flow": dcf,
        },
        "model_versions": model_versions,
        "leverage_band": leverage_band,
        "probabilistic_head": {
            "take_trade_prob": signal_row.get("take_trade_prob"),
            "probability_0_1": signal_row.get("probability_0_1"),
            "decision_confidence_0_1": signal_row.get("decision_confidence_0_1"),
            "model_uncertainty_0_1": signal_row.get("model_uncertainty_0_1"),
        },
    }


def initial_outcomes_json(signal_row: dict[str, Any]) -> dict[str, Any]:
    """Outcome-Lanes: null = nicht anwendbar/noch unbekannt."""
    ta = str(signal_row.get("trade_action") or "").strip().lower()
    lane = str(signal_row.get("meta_trade_lane") or "").strip().lower()
    base: dict[str, Any] = {
        "paper": {"lane": "paper", "phase": "none"},
        "shadow": None,
        "live_mirror": None,
        "counterfactual": None,
    }
    if lane == "shadow":
        base["shadow"] = {"lane": "shadow", "phase": "awaiting_or_skipped"}
    if lane == "live":
        base["live_mirror"] = {"lane": "live", "phase": "awaiting_or_skipped"}

    if ta == "do_not_trade":
        base["counterfactual"] = {
            "kind": "no_trade_at_decision",
            "trade_action": ta,
            "note_de": "Keine Ausfuehrung aufgrund finaler Pipeline; Outcome anderer Lanes typischerweise null.",
        }
    elif ta == "allow_trade":
        base["paper"]["phase"] = "eligible"
        base["counterfactual"] = {
            "kind": "trade_allowed_counterfactual_bucket",
            "note_de": "Platz fuer spaetere Counterfactual-Labels (missed move) ohne Execution.",
        }

    return base
