"""
Leverage-indexiertes Stop-Budget vs. Ausfuehrbarkeit (Tick, Spread, ATR, Slippage).

Kein LLM: rein deterministische Gates fuer institutionelles Audit und Learning.
"""

from __future__ import annotations

import math
from typing import Any

from signal_engine.config import SignalEngineSettings
from signal_engine.product_family_risk import effective_min_leverage, market_family_from_signal_row
from signal_engine.scoring.risk_score import _first_geometry

STOP_BUDGET_POLICY_VERSION = "stop-budget-v2"


def canonical_stop_budget_curve_descriptor(settings: SignalEngineSettings) -> dict[str, Any]:
    """End-to-end kanonische Kurve: Anchor-Hebel max 1.0%, linear enger bis Floor 0.10 %."""
    anchor = max(1, int(settings.stop_budget_anchor_leverage))
    high_l = max(anchor + 1, int(settings.stop_budget_high_leverage_floor))
    return {
        "anchor_leverage": anchor,
        "max_stop_fraction_at_anchor": float(settings.stop_budget_max_pct_at_anchor),
        "floor_stop_fraction_at_high_leverage": float(settings.stop_budget_floor_pct),
        "high_leverage_reference": high_l,
        "interpolation": "linear_in_leverage_between_anchor_and_reference",
        "semantics_de": (
            f"Bis {anchor}x maximal {float(settings.stop_budget_max_pct_at_anchor)*100:.2f} % Stop-Distanz; "
            f"bis Referenz-Hebel {high_l}x linear gegen {float(settings.stop_budget_floor_pct)*100:.2f} % — "
            "nur soweit Tick/Spread/Impact/ATR/Slippage/Liquidation/MAE ausfuehrbar."
        ),
    }


def collect_exit_family_budget_alternatives(signal_row: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Spezialisten-Vorschlaeg fuer weniger enge Stop-Budgets / andere Exit-Familien
    (Schritt 2 der Aufloesung wenn Hebelreduktion nicht reicht).
    """
    rj = signal_row.get("reasons_json")
    if not isinstance(rj, dict):
        return []
    spec = rj.get("specialists")
    if not isinstance(spec, dict):
        return []
    raw: list[dict[str, Any]] = []
    for key, block in spec.items():
        if not isinstance(block, dict):
            continue
        prop = block.get("proposal")
        if not isinstance(prop, dict):
            continue
        eid = prop.get("exit_family_primary")
        sb = prop.get("stop_budget_0_1")
        if isinstance(eid, str) and eid.strip():
            raw.append(
                {
                    "source": key,
                    "exit_family_primary": eid.strip(),
                    "stop_budget_0_1": float(sb) if isinstance(sb, (int, float)) else None,
                }
            )
    by_fam: dict[str, dict[str, Any]] = {}
    for item in raw:
        fam = item["exit_family_primary"]
        prev = by_fam.get(fam)
        if prev is None or (item.get("stop_budget_0_1") or 0) > (prev.get("stop_budget_0_1") or -1):
            by_fam[fam] = item
    return sorted(by_fam.values(), key=lambda x: (x.get("stop_budget_0_1") is None, -(x.get("stop_budget_0_1") or 0)))


def max_stop_budget_pct_for_leverage(leverage: int, settings: SignalEngineSettings) -> float:
    """Bei anchor-L (typ. 7) maximal max_pct (typ. 1%); nach oben linear bis floor_pct (typ. 0,1%)."""
    L = max(1, int(leverage))
    anchor = max(1, int(settings.stop_budget_anchor_leverage))
    high_l = max(anchor + 1, int(settings.stop_budget_high_leverage_floor))
    max_pct = float(settings.stop_budget_max_pct_at_anchor)
    floor_pct = float(settings.stop_budget_floor_pct)
    if L <= anchor:
        return max_pct
    if L >= high_l:
        return floor_pct
    span = float(high_l - anchor)
    t = (L - anchor) / span if span > 0 else 1.0
    return max_pct - t * (max_pct - floor_pct)


def _f(v: Any) -> float | None:
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _stop_mid_pct_from_close(
    *,
    close: float,
    stop_geo: dict[str, Any],
    direction: str,
) -> tuple[float | None, bool, list[str]]:
    """Directionaler Abstand Stop-Mitte zu Close in Prozent; wrong_side wenn Zone nicht protektiv."""
    reasons: list[str] = []
    try:
        lo = float(stop_geo["price_low"])
        hi = float(stop_geo["price_high"])
        mid = (lo + hi) / 2.0
    except (KeyError, TypeError, ValueError):
        return None, False, ["stop_geometry_invalid"]
    if close <= 0 or not math.isfinite(close):
        return None, False, ["invalid_close_for_stop_pct"]
    d = str(direction or "").strip().lower()
    dist = abs(mid - close) / close
    eps = 1e-9
    wrong = False
    if d == "long":
        if mid >= close - eps:
            wrong = True
            reasons.append("stop_zone_not_protective_long")
    elif d == "short":
        if mid <= close + eps:
            wrong = True
            reasons.append("stop_zone_not_protective_short")
    return dist, wrong, reasons


def _min_executable_stop_pct(
    *,
    settings: SignalEngineSettings,
    close: float,
    primary_feature: dict[str, Any] | None,
    direction: str,
    price_tick_size: str | None,
    expected_mae_bps: float | None,
    instrument: dict[str, Any] | None,
) -> tuple[float, dict[str, Any]]:
    """Konservativer Untergrenzen-Abstand in % (Mikrostruktur + ATR + MAE-Proxy)."""
    pf = primary_feature or {}
    parts: list[tuple[str, float]] = []
    detail: dict[str, Any] = {}

    tick = _f(price_tick_size)
    if tick is not None and tick > 0 and close > 0:
        steps = max(1, int(settings.stop_budget_tick_steps_min))
        v = (tick * float(steps)) / close
        parts.append(("tick", v))
        detail["tick_floor_pct"] = round(v, 8)

    spread_bps = _f(pf.get("spread_bps")) or 0.0
    spread_pct = spread_bps / 10_000.0
    mult = float(settings.stop_budget_spread_floor_mult)
    v = spread_pct * mult
    parts.append(("spread", v))
    detail["spread_floor_pct"] = round(v, 8)

    atrp = _f(pf.get("atrp_14"))
    if atrp is not None:
        v = abs(atrp) * float(settings.stop_budget_atr_floor_mult)
        parts.append(("atrp", v))
        detail["atrp_floor_pct"] = round(v, 8)

    if direction == "short":
        impact_bps = _f(pf.get("impact_sell_bps_10000")) or 0.0
    else:
        impact_bps = _f(pf.get("impact_buy_bps_10000")) or 0.0
    v = (impact_bps / 10_000.0) * float(settings.stop_budget_impact_floor_mult)
    parts.append(("impact", v))
    detail["impact_floor_pct"] = round(v, 8)

    exec_b = _f(pf.get("execution_cost_bps")) or 0.0
    vol_b = _f(pf.get("volatility_cost_bps")) or 0.0
    v = ((exec_b + vol_b) / 10_000.0) * float(settings.stop_budget_slippage_floor_mult)
    parts.append(("slippage_model", v))
    detail["slippage_floor_pct"] = round(v, 8)

    if expected_mae_bps is not None and expected_mae_bps > 0:
        v = (expected_mae_bps / 10_000.0) * float(settings.stop_budget_mae_structure_mult)
        parts.append(("mae_structure", v))
        detail["mae_structure_floor_pct"] = round(v, 8)

    raw = max((p[1] for p in parts), default=0.0)

    fam = str((instrument or {}).get("market_family") or "").strip().lower()
    fam_scale = 1.0
    if fam == "futures":
        fam_scale = float(settings.stop_budget_family_futures_floor_scale)
    elif fam == "margin":
        fam_scale = float(settings.stop_budget_family_margin_floor_scale)
    elif fam == "spot":
        fam_scale = float(settings.stop_budget_family_spot_floor_scale)
    detail["family_floor_scale"] = fam_scale

    # regime kommt aus signal_row, nicht instrument — caller patcht detail
    return raw * fam_scale, detail


def _regime_floor_scale(market_regime: str | None, settings: SignalEngineSettings) -> float:
    r = str(market_regime or "").strip().lower()
    if r in {"shock", "dislocation"}:
        return float(settings.stop_budget_regime_stress_floor_scale)
    if r in {"chop", "compression"}:
        return float(settings.stop_budget_regime_chop_floor_scale)
    return 1.0


def _stop_to_spread_ratio(stop_pct: float | None, spread_bps: float | None) -> float | None:
    if stop_pct is None or stop_pct <= 0:
        return None
    if spread_bps is None or spread_bps <= 0:
        return None
    spread_pct = spread_bps / 10_000.0
    if spread_pct <= 0:
        return None
    return round(stop_pct / spread_pct, 6)


def _scores(
    *,
    stop_pct: float,
    min_exec: float,
    budget: float,
) -> tuple[float, float, float]:
    """quality, executability, fragility in 0..1."""
    width = max(budget - min_exec, 1e-9)
    center = min_exec + 0.5 * width
    dist = abs(stop_pct - center)
    quality = max(0.0, min(1.0, 1.0 - dist / max(width, 1e-9)))
    if stop_pct + 1e-12 >= min_exec:
        executability = max(0.0, min(1.0, (stop_pct - min_exec) / max(budget - min_exec, 1e-9)))
    else:
        executability = max(0.0, min(1.0, stop_pct / max(min_exec, 1e-9)))
    if min_exec <= 1e-12:
        fragility = 0.5
    elif stop_pct < min_exec:
        fragility = max(0.0, min(1.0, 1.0 - stop_pct / min_exec))
    else:
        fragility = max(0.0, min(1.0, min_exec / max(stop_pct, 1e-9)))
    return round(quality, 6), round(executability, 6), round(fragility, 6)


def assess_stop_budget_policy(
    *,
    settings: SignalEngineSettings,
    signal_row: dict[str, Any],
    drawings: list[dict[str, Any]],
    last_close: float | None,
    primary_feature: dict[str, Any] | None,
    instrument_execution: dict[str, Any] | None,
    stop_trigger_type: str,
) -> dict[str, Any]:
    """
    Ergebnis inkl. Audit-Feldern; bei blocked/leverage_reduced muss der Aufrufer db_row anpassen.

    Aufloesungsreihenfolge bei Konflikten: Hebel reduzieren -> andere Exit-Familie pruefen (Audit) ->
    do_not_trade (durch Aufrufer bei blocked).
    """
    canonical_curve = canonical_stop_budget_curve_descriptor(settings)
    base_audit: dict[str, Any] = {
        "policy_version": STOP_BUDGET_POLICY_VERSION,
        "outcome": "skipped",
        "stop_distance_pct": None,
        "stop_budget_max_pct_allowed": None,
        "stop_min_executable_pct": None,
        "stop_to_spread_ratio": None,
        "stop_quality_0_1": None,
        "stop_executability_0_1": None,
        "stop_fragility_0_1": None,
        "gate_reasons_json": [],
        "canonical_stop_budget_curve": canonical_curve,
        "resolution_ladder_json": [],
        "exit_family_alternatives_json": [],
        "stop_resolution_order_de": (
            "1) Hebel reduzieren bis Stop in hebel-indexiertes Budget passt; "
            "2) sonst weniger enge Exit-/Playbook-Familie waehlen (Spezialisten-Alternativen im Audit); "
            "3) sonst do_not_trade — kein Trade erzwingen fuer hohen Hebel."
        ),
    }

    if not getattr(settings, "stop_budget_policy_enabled", True):
        base_audit["outcome"] = "audit_only"
        base_audit["gate_reasons_json"] = ["stop_budget_policy_disabled"]
        base_audit["resolution_ladder_json"] = [{"phase": "policy_disabled"}]
        return base_audit

    direction = str(signal_row.get("direction") or "").strip().lower()
    trade_action = str(signal_row.get("trade_action") or "").strip().lower()
    if trade_action != "allow_trade" or direction not in {"long", "short"}:
        base_audit["outcome"] = "skipped"
        base_audit["gate_reasons_json"] = ["stop_budget_not_applicable_trade_state"]
        base_audit["resolution_ladder_json"] = [{"phase": "not_applicable_trade_state"}]
        return base_audit

    close = last_close
    if close is None or close <= 0 or not math.isfinite(close):
        base_audit["outcome"] = "blocked"
        base_audit["gate_reasons_json"] = ["stop_budget_missing_close"]
        base_audit["resolution_ladder_json"] = [{"phase": "blocked_missing_close"}]
        return base_audit

    stop_geo = _first_geometry(drawings, "stop_zone")
    if stop_geo is None:
        base_audit["outcome"] = "blocked"
        base_audit["gate_reasons_json"] = ["stop_budget_missing_stop_zone"]
        base_audit["resolution_ladder_json"] = [{"phase": "blocked_missing_stop_zone"}]
        return base_audit

    stop_pct, wrong_side, geo_reasons = _stop_mid_pct_from_close(
        close=close, stop_geo=stop_geo, direction=direction
    )
    if stop_pct is None:
        base_audit["outcome"] = "blocked"
        base_audit["gate_reasons_json"] = geo_reasons
        base_audit["resolution_ladder_json"] = [{"phase": "blocked_invalid_stop_geometry"}]
        return base_audit

    if wrong_side:
        base_audit["outcome"] = "blocked"
        base_audit["stop_distance_pct"] = round(stop_pct, 8)
        base_audit["gate_reasons_json"] = geo_reasons
        base_audit["stop_fragility_0_1"] = 1.0
        base_audit["resolution_ladder_json"] = [
            {"phase": "stop_geometry_evaluated"},
            {"phase": "blocked_non_protective_stop", "reasons": geo_reasons},
        ]
        return base_audit

    snap = signal_row.get("source_snapshot_json")
    snap = snap if isinstance(snap, dict) else {}
    instr = snap.get("instrument")
    instr_d = instr if isinstance(instr, dict) else {}
    exec_meta = instrument_execution if isinstance(instrument_execution, dict) else {}
    tick = exec_meta.get("price_tick_size")

    mae_bps = _f(signal_row.get("expected_mae_bps"))
    min_exec_raw, floor_detail = _min_executable_stop_pct(
        settings=settings,
        close=close,
        primary_feature=primary_feature,
        direction=direction,
        price_tick_size=str(tick) if tick is not None else None,
        expected_mae_bps=mae_bps,
        instrument=instr_d,
    )
    regime_scale = _regime_floor_scale(signal_row.get("market_regime"), settings)
    floor_detail["regime_floor_scale"] = regime_scale
    min_exec = min_exec_raw * regime_scale
    min_exec = max(min_exec, float(settings.stop_budget_min_executable_floor_pct))

    spread_bps = _f((primary_feature or {}).get("spread_bps"))
    sts = _stop_to_spread_ratio(stop_pct, spread_bps)

    allowed = int(signal_row.get("allowed_leverage") or 0)
    min_lev = max(
        1,
        int(
            effective_min_leverage(
                market_family_from_signal_row(signal_row),
                settings.risk_allowed_leverage_min,
            )
        ),
    )

    resolution_ladder: list[dict[str, Any]] = [
        {"order": 1, "phase": "canonical_budget_curve", "descriptor": canonical_curve},
        {
            "order": 2,
            "phase": "executable_floor_microstructure",
            "stop_distance_pct": round(stop_pct, 8),
            "min_executable_pct": round(min_exec, 8),
            "floor_detail": floor_detail,
        },
    ]

    hybrid = snap.get("hybrid_decision")
    hybrid = hybrid if isinstance(hybrid, dict) else {}
    liq_stress = None
    la = hybrid.get("leverage_allocator")
    if isinstance(la, dict):
        mi = la.get("market_inputs")
        if isinstance(mi, dict):
            liq_stress = _f(mi.get("liquidation_proximity_stress_0_1"))

    mark_basis_note: str | None = None
    mib = _f((primary_feature or {}).get("mark_index_spread_bps"))
    if str(stop_trigger_type).strip().lower() == "mark_price":
        mark_basis_note = (
            f"trigger=mark_price; mark_index_spread_bps={mib}"
            if mib is not None
            else "trigger=mark_price; mark_index_spread_bps_unavailable"
        )
    else:
        mark_basis_note = f"trigger={stop_trigger_type}"

    def _blocked_audit(reasons: list[str]) -> dict[str, Any]:
        q0, e0, f0 = _scores(stop_pct=stop_pct, min_exec=min_exec, budget=max(stop_pct, min_exec))
        ladder_out = list(resolution_ladder)
        ex_alts: list[dict[str, Any]] = []
        if any("unsatisfiable" in r for r in reasons):
            ex_alts = collect_exit_family_budget_alternatives(signal_row)
            ladder_out.append(
                {
                    "order": len(ladder_out) + 1,
                    "phase": "exit_family_alternatives_ranked",
                    "note_de": "Hebelreduktion reicht nicht; pruefe andere Exit-Familien.",
                    "candidates": ex_alts,
                }
            )
        ladder_out.append(
            {
                "order": len(ladder_out) + 1,
                "phase": "outcome",
                "result": "blocked",
                "gate_reasons_json": reasons,
            }
        )
        return {
            **base_audit,
            "outcome": "blocked",
            "stop_distance_pct": round(stop_pct, 8),
            "stop_budget_max_pct_allowed": round(max_stop_budget_pct_for_leverage(allowed, settings), 8),
            "stop_min_executable_pct": round(min_exec, 8),
            "stop_to_spread_ratio": sts,
            "stop_quality_0_1": q0,
            "stop_executability_0_1": e0,
            "stop_fragility_0_1": f0,
            "floor_detail": floor_detail,
            "mark_trigger_note": mark_basis_note,
            "liquidation_proximity_stress_0_1": liq_stress,
            "leverage_before": allowed,
            "gate_reasons_json": reasons,
            "resolution_ladder_json": ladder_out,
            "exit_family_alternatives_json": ex_alts,
        }

    global_max = float(settings.stop_budget_max_pct_at_anchor)
    if stop_pct > global_max + 1e-12:
        resolution_ladder.append({"phase": "global_anchor_cap_check", "failed": True})
        return _blocked_audit(
            [
                "stop_distance_exceeds_global_max_budget",
                f"stop_pct={stop_pct:.6f}_max_anchor_budget={global_max:.6f}",
            ]
        )

    if (
        float(settings.stop_budget_liquidation_stress_block) > 0
        and liq_stress is not None
        and liq_stress >= float(settings.stop_budget_liquidation_stress_block)
        and stop_pct <= float(settings.stop_budget_liquidation_tight_stop_max_pct)
    ):
        resolution_ladder.append({"phase": "liquidation_proximity_vs_tight_stop", "failed": True})
        return _blocked_audit(
            [
                "stop_too_tight_vs_liquidation_stress",
                f"liq_stress={liq_stress:.4f}_stop_pct={stop_pct:.6f}",
            ]
        )

    if stop_pct + 1e-12 < min_exec and settings.stop_budget_hard_fragility_abstain:
        resolution_ladder.append({"phase": "executable_floor_violation", "failed": True})
        return _blocked_audit(
            [
                "stop_fragile_below_executable_floor",
                f"stop_pct={stop_pct:.6f}_min_exec={min_exec:.6f}",
            ]
        )

    resolution_ladder.append(
        {
            "order": 3,
            "phase": "leverage_budget_fit_scan",
            "leverage_start": allowed,
            "leverage_floor": min_lev,
        }
    )
    L_try = max(allowed, min_lev)
    best_l: int | None = None
    best_budget = 0.0
    while L_try >= min_lev:
        b = max_stop_budget_pct_for_leverage(L_try, settings)
        if stop_pct <= b + 1e-12:
            best_l = L_try
            best_budget = b
            break
        L_try -= 1

    if best_l is None:
        return _blocked_audit(
            [
                "stop_budget_unsatisfiable_at_min_leverage",
                f"stop_pct={stop_pct:.6f}_Lmin={min_lev}",
            ]
        )

    resolution_ladder.append(
        {
            "order": 4,
            "phase": "leverage_fit_result",
            "selected_leverage": best_l,
            "budget_at_selected_pct": round(best_budget, 8),
            "leverage_reduced_vs_signal": best_l < allowed,
        }
    )

    q, e, frag = _scores(stop_pct=stop_pct, min_exec=min_exec, budget=max(best_budget, min_exec))
    ladder_ok = list(resolution_ladder)
    ladder_ok.append({"order": len(ladder_ok) + 1, "phase": "outcome", "result": "passed"})
    audit: dict[str, Any] = {
        **base_audit,
        "outcome": "passed",
        "stop_distance_pct": round(stop_pct, 8),
        "stop_budget_max_pct_allowed": round(best_budget, 8),
        "stop_min_executable_pct": round(min_exec, 8),
        "stop_to_spread_ratio": sts,
        "stop_quality_0_1": q,
        "stop_executability_0_1": e,
        "stop_fragility_0_1": frag,
        "floor_detail": floor_detail,
        "mark_trigger_note": mark_basis_note,
        "liquidation_proximity_stress_0_1": liq_stress,
        "leverage_before": allowed,
        "gate_reasons_json": [],
        "resolution_ladder_json": ladder_ok,
        "exit_family_alternatives_json": [],
    }

    if best_l < allowed:
        audit["outcome"] = "leverage_reduced"
        audit["leverage_after"] = best_l
        audit["gate_reasons_json"] = [
            "stop_budget_required_leverage_reduction",
            f"from_{allowed}_to_{best_l}",
        ]
        audit["resolution_ladder_json"] = ladder_ok[:-1] + [
            {
                "order": len(ladder_ok),
                "phase": "leverage_reduction_applied",
                "from_leverage": allowed,
                "to_leverage": best_l,
            },
            {"order": len(ladder_ok) + 1, "phase": "outcome", "result": "leverage_reduced"},
        ]

    return audit
