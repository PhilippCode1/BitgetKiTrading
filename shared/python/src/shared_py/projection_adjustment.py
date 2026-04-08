"""
Mehrdimensionale Prognose-Anreicherung: Modell-Rohtreffer (Return, MAE, MFE) werden
um Mikrostruktur (Spread, Execution, Impact) und konservative Slippage-Puffer ergaenzt.

Die effektiven Groessen fliessen in Hybrid-Gates und Hebel-Caps; Rohwerte bleiben
in target_projection_summary fuer Audit verfuegbar.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

PROJECTION_ADJUSTMENT_VERSION = "1.0.0"


def _f(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def apply_projection_cost_adjustment(
    *,
    raw_return_bps: float | None,
    raw_mae_bps: float | None,
    raw_mfe_bps: float | None,
    direction: str,
    primary_tf: Mapping[str, Any] | None,
    adverse_slippage_mult: float = 0.35,
    favorable_slippage_mult: float = 0.25,
    safety_buffer_mult: float = 0.12,
) -> dict[str, Any]:
    """
    Netto-Return nach Roundtrip-Kosten; adverse MFE/MAE mit Richtungs-Impact aufgeblasen;
    konservativer Stop-Puffer in bps (fuer Exit-Planung / Dokumentation).
    """
    d = str(direction or "").strip().lower()
    pf = dict(primary_tf) if isinstance(primary_tf, Mapping) else {}
    spread = _f(pf.get("spread_bps")) or 0.0
    exec_cost = _f(pf.get("execution_cost_bps")) or 0.0
    vol_cost = _f(pf.get("volatility_cost_bps")) or 0.0
    if d == "short":
        impact = _f(pf.get("impact_sell_bps_10000")) or 0.0
    else:
        impact = _f(pf.get("impact_buy_bps_10000")) or 0.0

    half_spread = 0.5 * max(spread, 0.0)
    round_trip_micro = max(0.0, exec_cost + vol_cost + 2.0 * half_spread)

    raw_r = raw_return_bps
    raw_a = raw_mae_bps
    raw_f = raw_mfe_bps

    net_return = None
    if raw_r is not None:
        net_return = float(raw_r) - round_trip_micro

    adverse_slip = adverse_slippage_mult * max(0.0, impact + half_spread)
    favorable_slip = favorable_slippage_mult * max(0.0, impact + half_spread)

    eff_mae = None
    if raw_a is not None:
        eff_mae = max(0.0, float(raw_a) + adverse_slip)

    eff_mfe = None
    if raw_f is not None:
        eff_mfe = max(0.0, float(raw_f) - favorable_slip)

    safety_stop_buffer_bps = None
    if eff_mae is not None:
        safety_stop_buffer_bps = eff_mae * (1.0 + safety_buffer_mult) + half_spread

    return {
        "version": PROJECTION_ADJUSTMENT_VERSION,
        "round_trip_cost_bps": round(round_trip_micro, 6),
        "adverse_slippage_addon_bps": round(adverse_slip, 6),
        "favorable_slippage_discount_bps": round(favorable_slip, 6),
        "model_raw_bps": {
            "expected_return_bps": raw_r,
            "expected_mae_bps": raw_a,
            "expected_mfe_bps": raw_f,
        },
        "effective_bps": {
            "expected_return_bps": None if net_return is None else round(net_return, 6),
            "expected_mae_bps": None if eff_mae is None else round(eff_mae, 6),
            "expected_mfe_bps": None if eff_mfe is None else round(eff_mfe, 6),
        },
        "safety_stop_buffer_bps": None
        if safety_stop_buffer_bps is None
        else round(float(safety_stop_buffer_bps), 6),
        "inputs_used": {
            "spread_bps": spread,
            "execution_cost_bps": exec_cost,
            "volatility_cost_bps": vol_cost,
            "impact_bps_10000": impact,
            "direction": d or None,
        },
    }


def liquidation_proximity_stress_0_1(
    *,
    effective_adverse_bps: float | None,
    preview_leverage: int,
    maintenance_headroom: float = 0.82,
) -> float | None:
    """
    Grobe Naeherung: zulaessige adverse Preisbewegung (in bps) vor hohem Liquidationsstress
    skaliert mit 1/L; MAE_eff / safe_room -> 0..1. Kein Exchange-spezifisches MM,
    nur fuer relative Caps und Monitoring.
    """
    if effective_adverse_bps is None or preview_leverage < 1:
        return None
    if effective_adverse_bps <= 0:
        return 0.0
    lev = float(preview_leverage)
    safe_room = (10000.0 / lev) * max(0.1, min(1.0, maintenance_headroom))
    return max(0.0, min(1.0, float(effective_adverse_bps) / max(safe_room, 1e-6)))


def cap_from_liquidation_stress(
    *,
    stress_0_1: float | None,
    risk_max: int,
    stress_floor: float = 0.78,
) -> int | None:
    """Skaliert effektives Hebel-Maximum runter, wenn Stress hoch (ab stress_floor)."""
    if stress_0_1 is None or risk_max < 1:
        return None
    s = float(stress_0_1)
    if s <= stress_floor:
        return risk_max
    span = max(1e-6, 1.0 - stress_floor)
    factor = max(0.0, min(1.0, (1.0 - s) / span))
    capped = max(1, int(math.floor(risk_max * (0.35 + 0.65 * factor))))
    return min(capped, risk_max)
