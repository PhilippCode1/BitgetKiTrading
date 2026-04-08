"""
Gemeinsamer Hebel-/Exposure-Allocator (Edge, Stop-Distanz, Volatilitaet, Tiefe, Kontohitze, Unsicherheit).

Ziel: Hebel nicht als isolierte Zahl, sondern konsistent mit Positionsgroesse/Notional-Budget
und Ausfuehrbarkeit enger Stops. Keine LLMs.

Semantik:
- **allowed_leverage** / **recommended_leverage**: unveraendert aus Hybrid + Stop-Budget (Engine-Obergrenze
  bzw. Betriebspunkt).
- **execution_leverage_cap**: Obergrenze fuer *unbeaufsichtigte* Auto-Execution (Shadow/Paper-Default,
  Live nur wenn nicht manuell freigegeben); immer <= recommended.
- **mirror_leverage**: Referenz fuer explizit bestaetigte Realtrades (volles Signal-Ziel nach allen Gates,
  typisch = recommended wenn Trade erlaubt).
"""

from __future__ import annotations

import math
from typing import Any, Mapping

UNIFIED_LEVERAGE_ALLOCATOR_VERSION = "unified-lev-v2"


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int | None:
    if x in (None, ""):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _prior_signals_count(signal_row: Mapping[str, Any], source_snapshot: Mapping[str, Any]) -> int | None:
    ev = source_snapshot.get("instrument_evidence_json")
    if isinstance(ev, dict):
        v = _i(ev.get("prior_signal_count"))
        if v is not None:
            return v
    v2 = _i(signal_row.get("instrument_prior_signal_count"))
    if v2 is not None:
        return v2
    return None


def _family_max_cap(settings: Any, market_family: str) -> int | None:
    mf = str(market_family or "").strip().lower()
    attr = {
        "spot": "leverage_family_max_cap_spot",
        "margin": "leverage_family_max_cap_margin",
        "futures": "leverage_family_max_cap_futures",
    }.get(mf)
    if not attr:
        return None
    return _i(getattr(settings, attr, None))


def _stop_distance_leverage_cap(
    *,
    stop_distance_pct: float | None,
    risk_max: int,
    min_lev: int,
    scale_bps: float,
) -> int | None:
    if stop_distance_pct is None or stop_distance_pct <= 0 or scale_bps <= 0:
        return None
    stop_bps = stop_distance_pct * 10000.0
    raw = int(scale_bps / stop_bps)
    return max(0, min(risk_max, raw))


def _risk_acct_from_source_snapshot(snap: Mapping[str, Any]) -> dict[str, Any]:
    r = snap.get("risk_account_snapshot")
    if isinstance(r, dict):
        return dict(r)
    return {}


def recompute_unified_leverage_allocation(
    *,
    allowed_leverage: int,
    recommended_leverage: int | None,
    stop_distance_pct: float | None,
    meta_trade_lane: str,
    trade_action: str,
    governor: Mapping[str, Any],
    risk_account_snapshot: Mapping[str, Any],
    signal_row: Mapping[str, Any],
    settings: Any,
) -> dict[str, Any]:
    min_lev = int(getattr(settings, "risk_allowed_leverage_min", 7))
    risk_max = int(
        max(min_lev, min(int(getattr(settings, "risk_allowed_leverage_max", 75)), 75)),
    )
    allowed = max(0, min(risk_max, int(allowed_leverage)))
    rec = recommended_leverage
    if rec is not None:
        rec = max(0, min(risk_max, int(rec)))
    allow_trade = str(trade_action or "").strip().lower() == "allow_trade"

    drivers: list[str] = []
    evidence_cap_breakdown: list[dict[str, Any]] = []

    family_cap = _family_max_cap(settings, str(signal_row.get("market_family") or ""))
    if family_cap is not None and family_cap >= 0:
        drivers.append("family_cap_considered")

    stop_pct = float(stop_distance_pct) if stop_distance_pct is not None else None
    scale_bps = float(getattr(settings, "leverage_stop_distance_scale_bps", 180.0))
    stop_lev_cap = _stop_distance_leverage_cap(
        stop_distance_pct=stop_pct,
        risk_max=risk_max,
        min_lev=min_lev,
        scale_bps=scale_bps,
    )
    if stop_lev_cap is not None:
        drivers.append("stop_distance_compatibility_cap")

    snap = signal_row.get("source_snapshot_json")
    snap_d = snap if isinstance(snap, dict) else {}
    prior_n = _prior_signals_count(signal_row, snap_d)
    cold_threshold = int(getattr(settings, "leverage_cold_start_prior_signals_threshold", 20))
    cold_cap = int(getattr(settings, "leverage_cold_start_max_cap", 12))
    cold_active = prior_n is None or prior_n < cold_threshold
    cold_effective_cap = cold_cap if cold_active else risk_max
    if cold_active:
        drivers.append("instrument_cold_start_or_missing_evidence")
    evidence_cap_breakdown.append(
        {
            "name": "instrument_cold_start_cap",
            "value": cold_effective_cap,
            "active": cold_active,
        }
    )

    div = _f(signal_row.get("shadow_divergence_0_1"))
    div_thr = float(getattr(settings, "leverage_shadow_divergence_soft_cap_threshold_0_1", 0.38))
    div_cap = int(getattr(settings, "leverage_shadow_divergence_soft_max_leverage", 14))
    shadow_cap = risk_max
    if div is not None and div >= div_thr:
        shadow_cap = min(shadow_cap, div_cap)
        drivers.append("shadow_divergence_soft_cap")
    evidence_cap_breakdown.append(
        {
            "name": "model_shadow_divergence_cap",
            "value": div_cap,
            "shadow_divergence_0_1": div,
            "active": div is not None and div >= div_thr,
        }
    )

    mu = _f(risk_account_snapshot.get("margin_utilization_0_1"))
    heat_thr = float(getattr(settings, "leverage_account_heat_margin_soft_threshold_0_1", 0.50))
    heat_shrink = float(getattr(settings, "leverage_account_heat_execution_shrink_0_1", 0.75))
    heat_active = mu is not None and mu >= heat_thr
    if heat_active:
        drivers.append("account_margin_heat_execution_shrink")
    evidence_cap_breakdown.append(
        {
            "name": "portfolio_margin_usage_shrink",
            "margin_utilization_0_1": mu,
            "heat_active": heat_active,
            "shrink_factor_0_1": heat_shrink if heat_active else None,
        }
    )

    base_exposure = float(governor.get("max_exposure_fraction_0_1") or 1.0)
    tight_thr = float(getattr(settings, "leverage_tight_stop_exposure_threshold_pct", 0.004))
    tight_fac = float(getattr(settings, "leverage_tight_stop_exposure_shrink_factor_0_1", 0.60))
    notional_frac = min(1.0, max(0.0, base_exposure))
    if stop_pct is not None and stop_pct > 0 and stop_pct < tight_thr:
        notional_frac = min(1.0, max(0.0, notional_frac * tight_fac))
        drivers.append("tight_stop_notional_shrink")

    lane = str(meta_trade_lane or "").strip().lower()
    auto_frac = float(getattr(settings, "leverage_auto_execution_fraction_of_recommended_0_1", 0.88))
    auto_sub = int(getattr(settings, "leverage_auto_execution_subtract_steps", 0))

    binding_caps: dict[str, int] = {}

    gov_cap = _i(governor.get("max_leverage_cap"))
    if gov_cap is not None:
        evidence_cap_breakdown.append(
            {
                "name": "risk_governor_model_quality_cap",
                "value": int(gov_cap),
                "source": "hybrid_decision.risk_governor.max_leverage_cap",
            }
        )

    if family_cap is not None:
        fc = min(allowed, family_cap)
        binding_caps["exchange_family_cap"] = fc
        evidence_cap_breakdown.append(
            {"name": "exchange_family_cap", "value": int(family_cap), "binding_value": fc}
        )
    if stop_lev_cap is not None:
        sc = min(allowed, stop_lev_cap)
        binding_caps["stop_distance_cap"] = sc
        evidence_cap_breakdown.append(
            {
                "name": "stop_slippage_structure_cap",
                "value": int(stop_lev_cap),
                "binding_value": sc,
                "source": "stop_distance_pct vs leverage_stop_distance_scale_bps",
            }
        )

    ddd = _f(risk_account_snapshot.get("daily_drawdown_0_1"))
    ddw = _f(risk_account_snapshot.get("weekly_drawdown_0_1"))
    dd_thr_d = float(getattr(settings, "risk_leverage_cap_daily_drawdown_threshold_0_1", 0.025))
    dd_thr_w = float(getattr(settings, "risk_leverage_cap_weekly_drawdown_threshold_0_1", 0.06))
    dd_max_lev = int(getattr(settings, "risk_leverage_max_under_drawdown", 10))
    drawdown_cap_active = False
    if ddd is not None and ddd >= dd_thr_d:
        drawdown_cap_active = True
    if ddw is not None and ddw >= dd_thr_w:
        drawdown_cap_active = True
    if drawdown_cap_active:
        dc = min(allowed, dd_max_lev)
        binding_caps["drawdown_kill_switch_cap"] = dc
        evidence_cap_breakdown.append(
            {
                "name": "drawdown_kill_switch_cap",
                "value": dd_max_lev,
                "binding_value": dc,
                "daily_drawdown_0_1": ddd,
                "weekly_drawdown_0_1": ddw,
            }
        )

    hd_snap = snap_d.get("hybrid_decision") if isinstance(snap_d.get("hybrid_decision"), dict) else {}
    la_snap = hd_snap.get("leverage_allocator") if isinstance(hd_snap.get("leverage_allocator"), dict) else {}
    mi_liq = la_snap.get("market_inputs") if isinstance(la_snap.get("market_inputs"), dict) else {}
    liq_stress = _f(mi_liq.get("liquidation_proximity_stress_0_1"))
    if liq_stress is not None and liq_stress >= 0.55:
        liq_cap = max(min_lev, min(allowed, 12))
        binding_caps["liquidation_buffer_soft_cap"] = liq_cap
        evidence_cap_breakdown.append(
            {
                "name": "liquidation_proximity_buffer_cap",
                "stress_0_1": liq_stress,
                "binding_value": liq_cap,
            }
        )

    synthetic_allowed = allowed
    if binding_caps:
        synthetic_allowed = min(synthetic_allowed, *binding_caps.values())

    execution_cap: int | None = None
    mirror_lev: int | None = None

    if allow_trade and rec is not None and rec >= min_lev:
        mirror_lev = rec
        from_fraction = int(math.floor(rec * auto_frac))
        from_sub = rec - auto_sub
        raw_exec = min(from_fraction, from_sub, rec, synthetic_allowed, cold_effective_cap, shadow_cap)
        if family_cap is not None:
            raw_exec = min(raw_exec, family_cap)
        if stop_lev_cap is not None:
            raw_exec = min(raw_exec, stop_lev_cap)
        raw_exec = min(raw_exec, allowed)
        if heat_active:
            raw_exec = int(math.floor(raw_exec * heat_shrink))
        raw_exec = min(raw_exec, rec, allowed)
        if raw_exec < min_lev and rec is not None and rec >= min_lev:
            if family_cap is None or family_cap >= min_lev:
                raw_exec = min_lev
        execution_cap = raw_exec
        if lane in {"shadow_only", "paper_only"}:
            drivers.append(f"meta_lane_{lane}_execution_conservative")
    elif allow_trade and rec is None:
        mirror_lev = None
        execution_cap = None
    else:
        mirror_lev = None
        execution_cap = None

    return {
        "version": UNIFIED_LEVERAGE_ALLOCATOR_VERSION,
        "allowed_leverage_echo": allowed,
        "recommended_leverage_echo": rec,
        "execution_leverage_cap": execution_cap,
        "mirror_leverage": mirror_lev,
        "max_position_notional_fraction_0_1": round(notional_frac, 6),
        "instrument_evidence_tier": "cold_start" if cold_active else "normal",
        "prior_signal_count": prior_n,
        "binding_caps_json": {k: int(v) for k, v in binding_caps.items()},
        "evidence_cap_breakdown_json": evidence_cap_breakdown,
        "drivers_json": sorted(set(drivers)),
        "stop_distance_pct_echo": round(stop_pct, 8) if stop_pct is not None else None,
        "account_margin_utilization_0_1": mu,
        "leverage_caps_semantics_de": (
            "Hebel nur aus Evidenz-Caps: Boersen-/Family-Limit, Governor-Modellmatrix, "
            "Liquidationsnaehe, Stop-Distanz, Slippage/Spread-Umgebung (ueber Tier/Stop), "
            "Drawdown-Kill-Switch, Portfolio-Margin-Nutzung."
        ),
    }


def refresh_unified_leverage_allocation_in_snapshot(
    *,
    db_row: dict[str, Any],
    settings: Any,
    governor: Mapping[str, Any] | None = None,
    risk_account_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Schreibt frische Unified-Allocation in source_snapshot.hybrid_decision.leverage_allocator."""
    snap = db_row.get("source_snapshot_json")
    if not isinstance(snap, dict):
        return None
    hd = snap.get("hybrid_decision")
    if not isinstance(hd, dict):
        return None
    la = hd.get("leverage_allocator")
    if not isinstance(la, dict):
        la = {}

    gov = governor if isinstance(governor, dict) else (hd.get("risk_governor") or {})
    if not isinstance(gov, dict):
        gov = {}

    acct: dict[str, Any]
    if isinstance(risk_account_snapshot, dict):
        acct = dict(risk_account_snapshot)
    else:
        acct = _risk_acct_from_source_snapshot(snap)

    assess = snap.get("stop_budget_assessment")
    stop_pct = None
    if isinstance(assess, dict) and assess.get("stop_distance_pct") is not None:
        stop_pct = _f(assess.get("stop_distance_pct"))
    if stop_pct is None and db_row.get("stop_distance_pct") is not None:
        stop_pct = _f(db_row.get("stop_distance_pct"))

    allowed = _i(db_row.get("allowed_leverage")) or 0
    rec = _i(db_row.get("recommended_leverage"))
    meta_lane = str(db_row.get("meta_trade_lane") or hd.get("meta_trade_lane") or "")
    trade_action = str(db_row.get("trade_action") or "")

    unified = recompute_unified_leverage_allocation(
        allowed_leverage=allowed,
        recommended_leverage=rec,
        stop_distance_pct=stop_pct,
        meta_trade_lane=meta_lane,
        trade_action=trade_action,
        governor=gov,
        risk_account_snapshot=acct if isinstance(acct, dict) else {},
        signal_row=db_row,
        settings=settings,
    )
    la2 = dict(la)
    la2["unified_leverage_allocation"] = unified
    hd2 = dict(hd)
    hd2["leverage_allocator"] = la2
    snap["hybrid_decision"] = hd2
    db_row["source_snapshot_json"] = snap
    return unified


def extract_unified_leverage_allocation_from_signal_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    snap = row.get("source_snapshot_json")
    if not isinstance(snap, dict):
        return None
    hd = snap.get("hybrid_decision")
    if not isinstance(hd, dict):
        return None
    la = hd.get("leverage_allocator")
    if not isinstance(la, dict):
        return None
    u = la.get("unified_leverage_allocation")
    return u if isinstance(u, dict) else None


def extract_execution_leverage_cap_from_signal_row(row: Mapping[str, Any]) -> int | None:
    u = extract_unified_leverage_allocation_from_signal_row(row)
    if not u:
        return None
    return _i(u.get("execution_leverage_cap"))


def extract_mirror_leverage_from_signal_row(row: Mapping[str, Any]) -> int | None:
    u = extract_unified_leverage_allocation_from_signal_row(row)
    if not u:
        return None
    return _i(u.get("mirror_leverage"))
