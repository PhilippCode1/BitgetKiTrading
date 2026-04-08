"""
Counterfactual-Strukturen aus E2E-Snapshots: reine Spezifikation fuer Replay/Forschung.

Keine Ausfuehrung, keine Strategieaenderung — beschreibt nur alternative Annahmen.
"""

from __future__ import annotations

import json
from typing import Any


def build_counterfactual_scenarios(snapshot_json: dict[str, Any] | None) -> list[dict[str, Any]]:
    """
    Liste deterministisch sortierter Szenarien fuer Dokumentation/Reports.

    Router: naechster Kandidat aus playbook counterfactual_candidates (falls vorhanden).
    Leverage: halbes empfohlenes Cap (Floor 1).
    Exit: Platzhalter fuer spaetere Exit-Familie.
    No-trade: harte Abbruch-Variante.
    """
    snap = snapshot_json or {}
    out: list[dict[str, Any]] = []

    spec = snap.get("proposal_and_votes") if isinstance(snap.get("proposal_and_votes"), dict) else {}
    pb = spec.get("specialists", {}).get("playbook_specialist") if isinstance(spec.get("specialists"), dict) else None
    cands: list[str] = []
    if isinstance(pb, dict):
        prop = pb.get("proposal") if isinstance(pb.get("proposal"), dict) else {}
        raw_c = prop.get("counterfactual_candidates")
        if isinstance(raw_c, list):
            cands = [str(x) for x in raw_c if x]

    if cands:
        out.append(
            {
                "scenario_id": "router_alternate_playbook_candidate",
                "description_de": "Router haette priorisierten alternativen Playbook-Kandidaten gewichten koennen",
                "alternate_playbook_id": cands[0],
                "candidate_pool": cands[:5],
            }
        )

    lev = snap.get("leverage_band") if isinstance(snap.get("leverage_band"), dict) else {}
    rec = lev.get("recommended_leverage")
    cap = lev.get("execution_leverage_cap")
    try:
        rec_f = float(rec) if rec is not None else None
    except (TypeError, ValueError):
        rec_f = None
    try:
        cap_f = float(cap) if cap is not None else None
    except (TypeError, ValueError):
        cap_f = None
    if rec_f is not None and rec_f > 0:
        half = max(1.0, rec_f * 0.5)
        out.append(
            {
                "scenario_id": "conservative_leverage_half_recommended",
                "description_de": "Konservativer Hebel: 50% des empfohlenen Leverage (min 1)",
                "hypothetical_recommended_leverage": half,
                "reference_recommended_leverage": rec_f,
                "reference_execution_cap": cap_f,
            }
        )

    exit_hint = spec.get("playbook_exit_hint") if isinstance(spec.get("playbook_exit_hint"), dict) else {}
    if exit_hint.get("exit_family_primary"):
        out.append(
            {
                "scenario_id": "alternate_exit_family_placeholder",
                "description_de": "Exit: andere Familie aus Ranked-Liste simulierbar (kein PnL hier)",
                "primary_exit_family": exit_hint.get("exit_family_primary"),
                "ranked_exit_families": exit_hint.get("exit_families_ranked"),
            }
        )

    final = snap.get("final_decision") if isinstance(snap.get("final_decision"), dict) else {}
    ta = str(final.get("trade_action") or "").strip().lower()
    if ta == "allow_trade":
        out.append(
            {
                "scenario_id": "counterfactual_no_trade_at_decision",
                "description_de": "Gleicher Kontext, harte no-trade-Variante (Safety-Abgleich)",
                "hypothetical_trade_action": "do_not_trade",
            }
        )

    out.sort(key=lambda x: str(x.get("scenario_id")))
    return out


def summarize_lane_outcomes(e2e_row: dict[str, Any]) -> dict[str, Any] | None:
    """Extrahiert Paper/Shadow/Live-Vergleich wenn geschlossene PnL vorhanden."""
    raw = e2e_row.get("outcomes_json")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        return None
    paper = raw.get("paper") if isinstance(raw.get("paper"), dict) else None
    shadow = raw.get("shadow") if isinstance(raw.get("shadow"), dict) else None
    live = raw.get("live_mirror") if isinstance(raw.get("live_mirror"), dict) else None

    def _pnl(block: dict[str, Any] | None) -> float | None:
        if not block or str(block.get("phase") or "") != "closed":
            return None
        p = block.get("pnl_net_usdt")
        try:
            return float(p) if p is not None else None
        except (TypeError, ValueError):
            return None

    pp, sp, lp = _pnl(paper), _pnl(shadow), _pnl(live)
    if pp is None and sp is None and lp is None:
        return None

    delta = None
    if pp is not None and sp is not None:
        delta = round(sp - pp, 8)

    return {
        "signal_id": str(e2e_row.get("signal_id")),
        "paper_pnl_net_usdt_closed": pp,
        "shadow_pnl_net_usdt_closed": sp,
        "live_mirror_pnl_net_usdt_closed": lp,
        "shadow_minus_paper_pnl_usdt": delta,
    }
