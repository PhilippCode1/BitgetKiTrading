"""
Meta-Decision-Kernel: fusioniert Evidence aus Hybrid, Risk-Governor, Spezialisten,
Stop/Ausfuehrbarkeit, Datenqualitaet und Unsicherheit zu genau einer finalen Meta-Aktion.

Zielgroesse: erwarteter Nutzen unter Risiko (kalibrierter Proxy), nicht maximale Aktivitaet.
Keine stille Operator-Ueberschreibung — siehe Bundle-Hinweis operator_override_audit_required_de.
"""

from __future__ import annotations

import math
from typing import Any

from signal_engine.config import SignalEngineSettings

META_DECISION_KERNEL_VERSION = "mdk-v1"

MDK_HIGH_UNCERTAINTY = "mdk_abstain_high_uncertainty"
MDK_POOR_CALIBRATION = "mdk_abstain_poor_calibration"
MDK_OOD = "mdk_abstain_ood"
MDK_SPECIALIST_DIVERGENCE = "mdk_abstain_specialist_divergence"
MDK_DATA_QUALITY = "mdk_abstain_data_quality"
MDK_STOP_EXECUTABLE = "mdk_abstain_stop_executability"
MDK_PORTFOLIO_RISK = "mdk_abstain_portfolio_risk_universal"
MDK_SHADOW_DIVERGENCE = "mdk_abstain_shadow_live_divergence"
MDK_NEGATIVE_EU = "mdk_abstain_negative_expected_utility"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def policy_block_hints(db_row: dict[str, Any]) -> bool:
    """Deterministische / Policy-Schicht (Drift, Gates, Playbook-Blacklist, Regime-Policy)."""
    rej = db_row.get("rejection_reasons_json") or []
    if isinstance(rej, list) and "online_drift_hard_block" in rej:
        return True
    rj = db_row.get("reasons_json")
    if isinstance(rj, dict):
        det = rj.get("deterministic_gates")
        if isinstance(det, dict) and det.get("rejection_state"):
            return True
    abst = db_row.get("abstention_reasons_json") or []
    if not isinstance(abst, list):
        return False
    for a in abst:
        if not isinstance(a, str):
            continue
        if a.startswith("playbook_blacklist:") or a.startswith("regime_policy:"):
            return True
        if a.startswith("family_block:"):
            return True
    return False


def _collect_evidence_abstentions(
    settings: SignalEngineSettings,
    db_row: dict[str, Any],
    snap: dict[str, Any],
    hd: dict[str, Any],
    spec_adv: dict[str, Any],
    rg: dict[str, Any],
) -> list[str]:
    codes: list[str] = []

    qg = snap.get("quality_gate") if isinstance(snap.get("quality_gate"), dict) else {}
    if qg.get("passed") is False:
        codes.append(MDK_DATA_QUALITY)

    unc_phase = str(db_row.get("uncertainty_gate_phase") or "").strip().lower()
    ug = snap.get("uncertainty_gate") if isinstance(snap.get("uncertainty_gate"), dict) else {}
    if not unc_phase:
        unc_phase = str(ug.get("gate_phase") or "full").strip().lower()
    if unc_phase in ("blocked", "abstain", "hold"):
        codes.append(MDK_HIGH_UNCERTAINTY)

    mu = _f(db_row.get("model_uncertainty_0_1"))
    if mu is not None and mu >= float(settings.model_max_uncertainty):
        codes.append(MDK_HIGH_UNCERTAINTY)

    if bool(db_row.get("model_ood_alert")):
        codes.append(MDK_OOD)
    ood = _f(db_row.get("model_ood_score_0_1"))
    if ood is not None and ood >= float(settings.model_ood_hard_abstain_score):
        codes.append(MDK_OOD)

    if settings.model_calibration_required:
        ttp = db_row.get("take_trade_prob")
        meth = db_row.get("take_trade_calibration_method")
        if ttp is not None and (not meth or not str(meth).strip()):
            codes.append(MDK_POOR_CALIBRATION)

    sd = _f(db_row.get("shadow_divergence_0_1"))
    if sd is not None and sd >= float(settings.model_shadow_divergence_hard_abstain):
        codes.append(MDK_SHADOW_DIVERGENCE)

    se = _f(db_row.get("stop_executability_0_1"))
    if se is not None and se < float(settings.mdk_stop_executability_min_0_1):
        codes.append(MDK_STOP_EXECUTABLE)

    univ = rg.get("universal_hard_block_reasons_json") or []
    if isinstance(univ, list) and len(univ) > 0:
        codes.append(MDK_PORTFOLIO_RISK)

    if spec_adv.get("hard_veto_recommended"):
        codes.append(MDK_SPECIALIST_DIVERGENCE)
    diss = _f(spec_adv.get("dissent_score_0_1"))
    if diss is not None and diss >= float(settings.mdk_specialist_dissent_abstain_0_1):
        codes.append(MDK_SPECIALIST_DIVERGENCE)
    for k in ("tri_way_veto_recommended", "edge_dispersion_veto_recommended"):
        if spec_adv.get(k):
            codes.append(MDK_SPECIALIST_DIVERGENCE)

    return list(dict.fromkeys(codes))


def expected_utility_proxy_0_1(db_row: dict[str, Any], hd: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    """Kalibrierter Nutzen-Proxy (kein Ersatz fuer echte Kalibrierungskurven; nur relative Skala)."""
    p = _f(hd.get("take_trade_prob_adjusted_0_1")) or _f(db_row.get("take_trade_prob"))
    er = _f(db_row.get("expected_return_bps"))
    mae = _f(db_row.get("expected_mae_bps"))
    mfe = _f(db_row.get("expected_mfe_bps"))
    unc = _f(db_row.get("model_uncertainty_0_1"))
    breakdown: dict[str, Any] = {
        "p_calibrated_or_raw": p,
        "expected_return_bps": er,
        "expected_mae_bps": mae,
        "expected_mfe_bps": mfe,
        "model_uncertainty_0_1": unc,
    }
    if p is None or er is None:
        return 0.0, {**breakdown, "note": "incomplete_model_io"}

    lam_mae = 0.015
    lam_mfe_tail = 0.0008
    lam_u = 0.85
    edge = p * er
    risk_pen = lam_mae * (mae or 0.0)
    tail_pen = lam_mfe_tail * max(0.0, -(mfe or 0.0))
    unc_pen = lam_u * (unc if unc is not None else 0.5)
    raw = edge - risk_pen - tail_pen - unc_pen * 50.0
    eu01 = _clamp01(0.5 + math.tanh(raw / 120.0) * 0.5)
    return eu01, {**breakdown, "raw_score": raw}


def apply_meta_decision_kernel(
    *,
    settings: SignalEngineSettings,
    db_row: dict[str, Any],
) -> dict[str, Any]:
    snap = db_row.get("source_snapshot_json")
    snap = snap if isinstance(snap, dict) else {}
    hd = snap.get("hybrid_decision")
    hd = hd if isinstance(hd, dict) else {}
    rg = hd.get("risk_governor")
    rg = rg if isinstance(rg, dict) else {}

    rj = db_row.get("reasons_json")
    rj = rj if isinstance(rj, dict) else {}
    spec = rj.get("specialists")
    spec = spec if isinstance(spec, dict) else {}
    spec_adv = spec.get("adversary_check")
    spec_adv = spec_adv if isinstance(spec_adv, dict) else {}
    spec_router = spec.get("router_arbitration")
    spec_router = spec_router if isinstance(spec_router, dict) else {}

    evidence = _collect_evidence_abstentions(settings, db_row, snap, hd, spec_adv, rg)

    eu01, eu_breakdown = expected_utility_proxy_0_1(db_row, hd)
    models_ok = db_row.get("take_trade_prob") is not None and all(
        db_row.get(k) is not None for k in ("expected_return_bps", "expected_mae_bps", "expected_mfe_bps")
    )
    if models_ok and eu01 < float(settings.mdk_min_expected_utility_proxy_0_1):
        evidence.append(MDK_NEGATIVE_EU)
    evidence = list(dict.fromkeys(evidence))

    prior_ta = str(db_row.get("trade_action") or "").strip().lower()
    kernel_forces_dnt = len(evidence) > 0
    policy_layer = policy_block_hints(db_row)

    live_blocks = rg.get("live_execution_block_reasons_json") or []
    live_blocks = live_blocks if isinstance(live_blocks, list) else []
    operator_gate = bool(spec_router.get("operator_gate_required"))

    effective_dnt = prior_ta == "do_not_trade" or kernel_forces_dnt

    if effective_dnt:
        meta_action = "blocked_by_policy" if policy_layer else "do_not_trade"
    elif operator_gate or live_blocks:
        meta_action = "operator_release_pending"
    elif str(db_row.get("meta_trade_lane") or "").strip().lower() == "candidate_for_live":
        meta_action = "candidate_for_live"
    else:
        meta_action = "allow_trade_candidate"

    bundle = {
        "version": META_DECISION_KERNEL_VERSION,
        "meta_decision_action": meta_action,
        "expected_utility_proxy_0_1": round(eu01, 6),
        "expected_utility_breakdown": eu_breakdown,
        "abstention_codes_evidence": evidence,
        "policy_layer_hint": policy_layer,
        "decision_control_flow_semantics_de": (
            "Kernel fusioniert Hybrid, Risk Engine, Spezialisten (Family/Cluster/Regime/Playbook), "
            "Stop/Microstructure, Datenqualitaet und Unsicherheit. "
            "Optimierung: erwarteter Nutzen unter Risiko (Proxy), nicht maximale Aktivitaet."
        ),
        "operator_override_audit_required_de": (
            "Von der Engine gesetzte blocked_by_policy oder do_not_trade duerfen nicht still "
            "ueberschrieben werden. Live-Freigabe nur als separate auditierte Operator-Aktion "
            "(operator_override_audit_json, execution_operator_releases / execution_journal)."
        ),
        "inputs_snapshot": {
            "trade_action_pre_kernel": prior_ta,
            "meta_trade_lane_pre_kernel": db_row.get("meta_trade_lane"),
            "kernel_forced_do_not_trade": kernel_forces_dnt,
            "live_execution_block_count": len(live_blocks),
            "operator_gate_required": operator_gate,
        },
    }

    return {
        "meta_decision_action": meta_action,
        "meta_decision_kernel_version": META_DECISION_KERNEL_VERSION,
        "meta_decision_bundle_json": bundle,
        "kernel_forces_do_not_trade": kernel_forces_dnt,
        "kernel_abstention_codes": evidence,
    }
