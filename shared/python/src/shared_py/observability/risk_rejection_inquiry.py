"""
Operatoren-Hilfspaket bei Risk-Ablehnungen (Multiturn-Assist).

Verknuepft Forensik (TradeLifecycle / Golden Record) mit Policy-Treffern
(Metrik vs. Limit) fuer konkrete KI-Antworten.
"""

from __future__ import annotations

import math
from typing import Any

from shared_py.observability.trade_lifecycle_audit import (
    build_golden_record_from_timeline,
)
from shared_py.observability.vpin_redis import VPIN_HARD_HALT_THRESHOLD_0_1

# Kanonisch fuer UI/API (Prompt 69) — interne Risk-Engine-Blocker mit Messwerten.
REJECTED_BY_RISK = "REJECTED_BY_RISK"

_NON_RISK_BLOCK_REASONS = frozenset(
    {
        "instrument_unknown",
        "instrument_not_tradeable",
        "instrument_session_not_tradeable",
        "symbol_not_allowed",
        "market_family_not_allowed",
        "product_type_not_allowed",
        "direction_not_actionable",
        "spot_short_not_supported",
        "survival_execution_lock",
        "meta_trade_lane_not_live_candidate",
        "missing_execution_plan",
        "missing_7x_approval",
        "live_submit_disabled",
        "exchange_health_unavailable",
        "live_trade_disabled",
        "live_safety_latch_active",
        "shadow_live_divergence_gate",
        "shadow_match_execution_id_required",
        "shadow_match_latch_miss",
    }
)


def _f(x: Any) -> float | None:
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, int | float) and not isinstance(x, bool):
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    try:
        v = float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _dget(obj: Any, *keys: str) -> Any:
    cur: Any = obj
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def is_rejected_by_risk(timeline: dict[str, Any]) -> bool:
    """
    Heuristik: Abbruch wegen Risk-Engine (do_not_trade) vs. technische/Produkt-Blocker.
    """
    d = timeline.get("decision")
    d = d if isinstance(d, dict) else {}
    action = str(d.get("decision_action") or "").strip().lower()
    if action != "blocked":
        return False
    reason = str(d.get("decision_reason") or "").strip()
    if reason in _NON_RISK_BLOCK_REASONS:
        return False
    rs = timeline.get("risk_snapshot")
    if isinstance(rs, dict):
        if str(rs.get("trade_action") or "").strip().lower() == "do_not_trade":
            return True
        st = str(rs.get("decision_state") or "").strip().lower()
        if st == "rejected":
            return True
    pay = d.get("payload_json")
    pay = pay if isinstance(pay, dict) else {}
    re = pay.get("risk_engine")
    re_ta = (
        str(re.get("trade_action") or "").strip().lower()
        if isinstance(re, dict)
        else ""
    )
    if isinstance(re, dict) and re_ta == "do_not_trade":
        return True
    if reason in (
        "shared_risk_blocked",
        "PORTFOLIO_EXPOSURE_EXCEEDED",
        "RISK_VPIN_HALT",
    ):
        return True
    if reason == "portfolio_live_execution_policy":
        return True
    return False


def _build_policy_hits_de(
    timeline: dict[str, Any], *, risk: dict[str, Any], lim: dict[str, Any]
) -> list[str]:
    hits: list[str] = []
    metrics = risk.get("metrics_json")
    m = metrics if isinstance(metrics, dict) else {}
    detail = risk.get("detail_json")
    det = detail if isinstance(detail, dict) else {}

    vpin = _f(m.get("vpin_toxicity_0_1"))
    if vpin is None:
        vpin = _f(_dget(m, "toxicity_features", "vpin_toxicity_0_1"))
    if vpin is None and isinstance(det, dict):
        vpin = _f(_dget(det, "metrics", "vpin_toxicity_0_1"))
    vthr = det.get("vpin_veto_threshold_0_1")
    lthr = lim.get("vpin_veto_threshold_0_1")
    thr = _f(vthr) or _f(lthr)
    ref = thr if thr is not None else float(VPIN_HARD_HALT_THRESHOLD_0_1)
    if vpin is not None:
        cmp_thr = ref
        st = "ueber" if vpin >= cmp_thr else "unter"
        hits.append(
            f"Orderflow/VPIN-Toxizitaet: Messwert {vpin:.2f} "
            f"(Referenz/Limit {cmp_thr:.2f}) — aktuell {st} dem Schwellen-Setup."
        )

    pmu = _f(m.get("projected_margin_usage_pct")) or _f(
        m.get("account_margin_usage_projected_0_1")
    )
    mmu = _f(
        lim.get("max_account_margin_usage") or lim.get("risk_max_account_margin_usage")
    )
    if pmu is not None and mmu is not None and pmu >= mmu:
        hits.append(
            f"Margin-Auslastung: projiziert {pmu:.1%} vs. Konto-Limit {mmu:.1%}."
        )
    elif pmu is not None and mmu is not None:
        hits.append(
            f"Margin-Auslastung: projiziert {pmu:.1%} (Konto-Obergrenze {mmu:.1%})."
        )

    pexp = m.get("portfolio_exposure")
    if isinstance(pexp, dict):
        le = _f(pexp.get("largest_position_risk_0_1"))
        lim_le = _f(
            pexp.get("max_largest_position_risk_0_1")
            or lim.get("risk_portfolio_live_max_largest_position_risk_0_1")
        )
        if le is not None and lim_le is not None:
            hits.append(
                "Portfolio-Exposure: groesstes Positionsrisiko "
                f"{le:.2f} (Deckel {lim_le:.2f})."
            )

    reasons = risk.get("reasons_json")
    rlist: list[str] = []
    if isinstance(reasons, list):
        rlist = [str(x) for x in reasons if isinstance(x, str | int | float)][:20]
    pr = str(risk.get("primary_reason") or det.get("decision_reason") or "")

    pfx = "PORTFOLIO_EXPOSURE" in pr.upper()
    pany = any("PORTFOLIO" in str(x).upper() for x in rlist)
    if pfx or pany:
        hits.append(
            "Policy: Portfolio-Exposure-Deckel (Notional/Cluster) — "
            "siehe Metriken/Reason-Codes."
        )
    vpin_block = "RISK_VPIN" in pr.upper() or (vpin is not None and vpin >= ref - 1e-9)
    if vpin_block:
        hits.append("Policy: Toxizitaet/Orderflow-Guard (VPIN) blockiert Eroeffnung.")

    d = timeline.get("decision")
    d = d if isinstance(d, dict) else {}
    oreason = str(d.get("decision_reason") or "")
    if oreason and oreason not in _NON_RISK_BLOCK_REASONS:
        hits.append(f"Broker-Entscheid: decision_reason={oreason!r}.")

    return [h for h in hits if h]


def build_risk_rejection_inquiry(timeline: dict[str, Any]) -> dict[str, Any]:
    """
    Kompaktes, assistenz-taugliches Paket inkl. Policy-Treffern in ganzen Saetzen.
    """
    d = timeline.get("decision")
    d = d if isinstance(d, dict) else {}
    rs = timeline.get("risk_snapshot")
    rs = rs if isinstance(rs, dict) else {}
    det = rs.get("detail_json")
    det = det if isinstance(det, dict) else {}
    lim: dict[str, Any] = {}
    lraw = det.get("limits")
    if isinstance(lraw, dict):
        lim = lraw
    mraw = rs.get("metrics_json")
    metrics = mraw if isinstance(mraw, dict) else {}
    by_risk = is_rejected_by_risk(timeline)
    code = REJECTED_BY_RISK if by_risk else None

    hits_de = _build_policy_hits_de(timeline, risk=rs, lim=lim) if by_risk else []

    return {
        "schema_version": "risk_rejection_inquiry_v1",
        "rejection_code": code,
        "rejected_by_risk_engine": by_risk,
        "decision": {
            "action": d.get("decision_action"),
            "reason": d.get("decision_reason"),
        },
        "risk_engine": {
            "trade_action": rs.get("trade_action"),
            "decision_state": rs.get("decision_state"),
            "primary_reason": rs.get("primary_reason") or det.get("decision_reason"),
            "reasons_json_head": (rs.get("reasons_json") or [])[:20]
            if isinstance(rs.get("reasons_json"), list)
            else [],
        },
        "limits_excerpt": {k: lim.get(k) for k in list(lim)[:32]},
        "metrics_excerpt": {
            "vpin_toxicity_0_1": metrics.get("vpin_toxicity_0_1")
            or _dget(metrics, "toxicity_features", "vpin_toxicity_0_1"),
            "projected_margin_usage_pct": metrics.get("projected_margin_usage_pct"),
            "position_notional_usdt": metrics.get("position_notional_usdt"),
        },
        "orchestrator_digest_de": (
            "Fasse mit konkreten Zahlen aus policy_hits_de und metrics_excerpt ab — "
            "keine Markt-Floskeln ohne Messwerte."
        ),
        "policy_hits_de": hits_de,
    }


def build_ops_risk_assist_context(timeline: dict[str, Any]) -> dict[str, Any]:
    """
    BFF/Assist: erlaubte keys fuer ops_risk
    (trade_lifecycle_golden, risk_rejection_inquiry, decision_brief).
    """
    d = timeline.get("decision")
    d = d if isinstance(d, dict) else {}
    golden = build_golden_record_from_timeline(timeline)
    inq = build_risk_rejection_inquiry(timeline)
    return {
        "schema_version": "ops_risk_assist_v1",
        "execution_id": str(timeline.get("execution_id") or ""),
        "decision_brief": {
            "execution_id": str(timeline.get("execution_id") or ""),
            "decision_action": d.get("decision_action"),
            "decision_reason": d.get("decision_reason"),
            "symbol": d.get("symbol"),
        },
        "trade_lifecycle_golden": golden,
        "risk_rejection_inquiry": inq,
    }
