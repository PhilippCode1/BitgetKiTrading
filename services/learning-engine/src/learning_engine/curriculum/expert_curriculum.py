"""
Curriculum fuer Spezialisten-Rollen: Cluster-Experten bei duennen Symbol-Daten.

Kein RL / keine Policy-Mutation — nur Trainings- und Promotions-Empfehlungen.
"""

from __future__ import annotations

from typing import Any

EXPERT_CURRICULUM_VERSION = "specialist-curriculum-v2"


def cluster_expert_key(*, market_family: str, market_regime: str) -> str:
    fam = (market_family or "unknown").strip().lower() or "unknown"
    reg = (market_regime or "unknown").strip().lower() or "unknown"
    return f"{fam}::{reg}"


def build_expert_curriculum_overlay(
    readiness_report: dict[str, Any],
    settings: Any,
) -> dict[str, Any]:
    """Ergaenzt specialist_readiness um Curriculum-Phasen und Degrade-Hinweise."""
    sym_audit = readiness_report.get("symbol_audit") or []
    thin_symbols = [
        x
        for x in sym_audit
        if isinstance(x, dict) and x.get("degrade_to_cluster_expert")
    ]
    fam_audit = readiness_report.get("family_audit") or []
    cl_audit = readiness_report.get("cluster_audit") or []
    reg_audit = readiness_report.get("regime_audit") or []
    pb_audit = readiness_report.get("playbook_audit") or []

    min_sym = int(getattr(settings, "specialist_symbol_min_rows", 500))
    min_cl = int(getattr(settings, "specialist_cluster_min_rows", 80))
    min_pb = int(getattr(settings, "specialist_playbook_min_rows", 50))
    min_reg = int(getattr(settings, "specialist_regime_min_rows", 60))
    min_fam = int(getattr(settings, "specialist_family_min_rows", 40))

    return {
        "curriculum_version": EXPERT_CURRICULUM_VERSION,
        "expert_tracks": [
            {
                "track_id": "family_expert",
                "min_rows_env": "SPECIALIST_FAMILY_MIN_ROWS",
                "min_rows": min_fam,
                "rows_source": "family_audit.n_after_gates",
            },
            {
                "track_id": "cluster_expert",
                "min_rows_env": "SPECIALIST_CLUSTER_MIN_ROWS",
                "min_rows": min_cl,
                "rows_source": "cluster_audit (market_family::market_regime)",
                "note_de": (
                    "Bevorzugt bei duennen Symbol-Daten "
                    "(symbol_audit.degrade_to_cluster_expert)."
                ),
            },
            {
                "track_id": "regime_expert",
                "min_rows_env": "SPECIALIST_REGIME_MIN_ROWS",
                "min_rows": min_reg,
                "rows_source": "regime_audit",
            },
            {
                "track_id": "playbook_expert",
                "min_rows_env": "SPECIALIST_PLAYBOOK_MIN_ROWS",
                "min_rows": min_pb,
                "rows_source": "playbook_audit (signal_snapshot_json)",
            },
            {
                "track_id": "symbol_expert",
                "min_rows_env": "SPECIALIST_SYMBOL_MIN_ROWS",
                "min_rows": min_sym,
                "rows_source": "symbol_audit",
                "note_de": "Nur bei nachgewiesener Mindestmenge; sonst Cluster-Pool.",
            },
        ],
        "degrade_summary": {
            "symbols_below_min_rows": thin_symbols,
            "families_below_min_rows": (
                readiness_report.get("families_below_min_rows") or []
            ),
            "clusters_below_min_rows": (
                readiness_report.get("clusters_below_min_rows") or []
            ),
            "regimes_below_min_rows": (
                readiness_report.get("regimes_below_min_rows") or []
            ),
            "playbooks_below_min_rows": (
                readiness_report.get("playbooks_below_min_rows") or []
            ),
        },
        "counts": {
            "family_segments": len(fam_audit),
            "cluster_segments": len(cl_audit),
            "regime_segments": len(reg_audit),
            "playbook_segments": len(pb_audit),
            "symbol_segments": len(sym_audit),
        },
    }
