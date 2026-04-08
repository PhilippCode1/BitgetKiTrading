"""
Einheitlicher Exit-Plan fuer Paper, Shadow und Live (gleiche fachliche Semantik).

Baut deterministische Exit-Beine aus Signal-Spalten, Stop-Budget-Audit und
End-Decision-Binding — kein starrer Einheits-RR: Take-Profit-Stufen leiten sich
aus erwartetem MFE/MAE und Exit-Familie ab.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

UNIFIED_EXIT_PLAN_VERSION = "unified-exit-v1"


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _family_trailing_mode(exit_family: str) -> str:
    ef = str(exit_family or "").strip().lower()
    if "runner" in ef or "trail" in ef:
        return "atr_chandelier"
    if "scale" in ef:
        return "staged_trail_after_be"
    return "swing_structure_trail"


def build_unified_exit_plan(
    *,
    signal_row: Mapping[str, Any],
    end_decision_binding: Mapping[str, Any] | None = None,
    stop_budget_assessment: Mapping[str, Any] | None = None,
    primary_feature: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Liefert maschinenlesbare Exit-Beine; Ausfuehrung bleibt Broker-seitig,
    aber Plan ist fuer alle Modi identisch serialisierbar.
    """
    edb = end_decision_binding if isinstance(end_decision_binding, dict) else {}
    sba = stop_budget_assessment if isinstance(stop_budget_assessment, dict) else {}
    pf = primary_feature if isinstance(primary_feature, dict) else {}

    direction = str(signal_row.get("direction") or "").strip().lower()
    exit_eff = str(
        edb.get("exit_family_effective_primary")
        or edb.get("exit_family_primary")
        or "target_ladder"
    ).strip()

    stop_pct = _f(sba.get("stop_distance_pct")) or _f(signal_row.get("stop_distance_pct"))
    mae_bps = _f(signal_row.get("expected_mae_bps"))
    mfe_bps = _f(signal_row.get("expected_mfe_bps"))
    atrp = _f(pf.get("atrp_14"))
    spread_bps = _f(pf.get("spread_bps"))

    # Initialer Schutz: zeichnerischer / auditierter Stop
    initial_stop = {
        "basis": "structured_stop_zone",
        "distance_pct_from_entry": round(stop_pct, 8) if stop_pct is not None else None,
        "expected_mae_bps_echo": mae_bps,
        "link_to_stop_budget_outcome": sba.get("outcome"),
        "resolution_ladder_ref": "stop_budget_assessment.resolution_ladder_json",
    }

    # Teil-TP: Anteile am MFE (kein fixes RR), staffeln
    partial_tp: list[dict[str, Any]] = []
    if mfe_bps is not None and mfe_bps > 0:
        for i, frac in enumerate((0.35, 0.65, 1.0), start=1):
            bps = mfe_bps * frac
            partial_tp.append(
                {
                    "leg_id": f"tp_mfe_{i}",
                    "fraction_of_position": {1: 0.25, 2: 0.35, 3: 0.4}[i],
                    "profit_capture_bps_from_entry": round(bps, 4),
                    "rationale_de": f"Erwartungs-MFE anteilig ({frac:.0%}), kein fixes RR",
                }
            )

    break_even = {
        "arm_after_first_partial_fill": True,
        "offset_bps": max(2.0, (spread_bps or 1.0) * 2.0) if spread_bps is not None else 4.0,
        "policy": "move_stop_to_entry_plus_costs",
    }

    trailing = {
        "mode": _family_trailing_mode(exit_eff),
        "activate_after_break_even": True,
        "atr_multiple": 1.15 if atrp is not None else None,
        "atrp_14_echo": atrp,
    }

    time_stop = {
        "max_hold_bars_default": 48,
        "scale_with_timeframe": True,
        "hard_flat_on_expiry": False,
        "notes_de": "Konkrete Bar-Anzahl vom Playbook/TF ableiten (Broker-Timer)",
    }

    structure_invalidation = {
        "trigger": "opposing_structure_break_or_mae_breach",
        "mae_bps_threshold": mae_bps,
        "flatten_fraction_0_1": 1.0,
    }

    vol_capture = {
        "mode": "widen_targets_on_low_atr_compress_tp_on_high_atr",
        "atrp_14": atrp,
        "spread_bps": spread_bps,
    }

    mfe_mae_family = {
        "primary_exit_family": exit_eff,
        "tp_leg_model": "mfe_fraction_ladder",
        "stop_leg_model": "min(structured_stop, mae_structure_floor_from_stop_budget)",
        "expected_mfe_bps": mfe_bps,
        "expected_mae_bps": mae_bps,
    }

    return {
        "version": UNIFIED_EXIT_PLAN_VERSION,
        "direction": direction if direction in {"long", "short"} else None,
        "initial_stop": initial_stop,
        "partial_take_profits": partial_tp,
        "break_even_shift": break_even,
        "trailing": trailing,
        "time_stop": time_stop,
        "structure_invalidation": structure_invalidation,
        "volatility_aware_profit_capture": vol_capture,
        "mfe_mae_tp_family": mfe_mae_family,
        "execution_semantics_de": (
            "Gleicher Plan-Typ fuer paper/shadow/live; Runtime-Modus steuert nur "
            "Submission/Spiegelung, nicht die fachliche Exit-Logik."
        ),
    }
