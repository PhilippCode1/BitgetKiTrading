"""
Schicht 5: Risiko aus Stop-/Ziel-Drawings, RR, Volatilitaet, Liquiditaet.
"""

from __future__ import annotations

import math
from typing import Any

from signal_engine.models import LayerScore, ScoringContext


def score_risk(
    ctx: ScoringContext,
    *,
    market_regime: str | None = None,
    regime_bias: str | None = None,
) -> LayerScore:
    notes: list[str] = []
    flags: list[str] = []
    base = 40.0
    drawings = ctx.drawings
    stop = _first_geometry(drawings, "stop_zone")
    targets = [d for d in drawings if d.get("type") == "target_zone"]
    liq = [d for d in drawings if d.get("type") == "liquidity_zone"]

    if stop is None:
        base -= 28.0
        flags.append("no_stop_drawing")
        notes.append("stop_zone_missing")
    else:
        base += 22.0
        notes.append("stop_zone_present")

    if not targets:
        base -= 18.0
        flags.append("no_target_zones")
        notes.append("targets_missing")
    else:
        base += 14.0
        notes.append(f"targets_count={len(targets)}")

    close = ctx.last_close
    rr = _reward_risk_ratio(close, stop, targets)
    if rr is not None and not math.isnan(rr):
        notes.append(f"reward_risk={rr:.3f}")
        if rr >= 2.0:
            base += 12.0
        elif rr >= 1.2:
            base += 6.0
        else:
            base -= 12.0
            flags.append("weak_reward_risk")
    else:
        notes.append("reward_risk_not_computable")
        base -= 8.0
        flags.append("rr_missing")

    feat = ctx.primary_feature
    if feat:
        atrp = feat.get("atrp_14")
        if atrp is not None:
            a = abs(float(atrp))
            if a > 0.25:
                base -= 10.0
                flags.append("high_atrp_volatile")
                notes.append("atrp_elevated")
            else:
                notes.append("atrp_moderate")

        spread_bps = feat.get("spread_bps")
        if spread_bps is not None:
            spread = float(spread_bps)
            if spread > 6.0:
                base -= 10.0
                flags.append("wide_spread")
                notes.append("spread_wide")
            elif spread <= 2.0:
                base += 3.0
                notes.append("spread_tight")

        execution_cost_bps = feat.get("execution_cost_bps")
        if execution_cost_bps is not None:
            execution_cost = float(execution_cost_bps)
            if execution_cost > 16.0:
                base -= 14.0
                flags.append("execution_cost_elevated")
                notes.append("execution_cost_high")
            elif execution_cost <= 5.0:
                base += 4.0
                notes.append("execution_cost_ok")

        depth_ratio = feat.get("depth_to_bar_volume_ratio")
        if depth_ratio is not None:
            ratio = float(depth_ratio)
            if ratio < 0.35:
                base -= 10.0
                flags.append("thin_orderbook_depth")
                notes.append("depth_vs_bar_volume_thin")
            elif ratio >= 1.0:
                base += 4.0
                notes.append("depth_vs_bar_volume_ok")

        funding_cost = feat.get("funding_cost_bps_window")
        if funding_cost is not None:
            funding = float(funding_cost)
            if funding > 1.25:
                base -= 6.0
                flags.append("funding_drag_elevated")
                notes.append("funding_cost_high")

        oi_delta = feat.get("open_interest_change_pct")
        if oi_delta is not None:
            oi_change = abs(float(oi_delta))
            if oi_change > 8.0:
                base -= 6.0
                flags.append("oi_crowding")
                notes.append("open_interest_shift_fast")

        liquidity_source = str(feat.get("liquidity_source") or "").strip()
        if liquidity_source and liquidity_source != "orderbook_levels":
            base -= 8.0
            flags.append("liquidity_fallback")
            notes.append(f"liquidity_source={liquidity_source}")

    if close is not None and liq:
        if _near_liquidity(close, liq):
            base -= 10.0
            flags.append("near_liquidity_zone")
            notes.append("price_near_liquidity")

    if market_regime == "trend":
        base += 6.0
        notes.append("regime_trend_support")
    elif market_regime == "breakout":
        base += 4.0
        notes.append("regime_breakout_context")
    elif market_regime == "compression":
        base -= 4.0
        flags.append("compression_regime_caution")
        notes.append("regime_compression_caution")
    elif market_regime == "chop":
        base -= 10.0
        flags.append("chop_regime")
        notes.append("regime_chop_noise")
    elif market_regime == "shock":
        base -= 18.0
        flags.append("shock_regime")
        notes.append("regime_shock_high_uncertainty")
    elif market_regime == "dislocation":
        base -= 15.0
        flags.append("dislocation_regime")
        notes.append("regime_dislocation_liquidity_stress")

    if regime_bias == "neutral" and market_regime in {"trend", "breakout"}:
        base -= 3.0
        notes.append("regime_bias_neutral")

    score = max(0.0, min(100.0, base))
    return LayerScore(score, notes, flags)


def _first_geometry(drawings: list[dict[str, Any]], dtype: str) -> dict[str, Any] | None:
    for d in drawings:
        if d.get("type") == dtype:
            g = d.get("geometry")
            if isinstance(g, dict):
                return g
    return None


def _reward_risk_ratio(
    close: float | None,
    stop_geo: dict[str, Any] | None,
    targets: list[dict[str, Any]],
) -> float | None:
    if close is None or stop_geo is None or not targets:
        return None
    try:
        stop_lo = float(stop_geo["price_low"])
        stop_hi = float(stop_geo["price_high"])
        stop_mid = (stop_lo + stop_hi) / 2.0
    except (KeyError, TypeError, ValueError):
        return None
    t0 = targets[0].get("geometry") or {}
    try:
        t_lo = float(t0["price_low"])
        t_hi = float(t0["price_high"])
        tgt_mid = (t_lo + t_hi) / 2.0
    except (KeyError, TypeError, ValueError):
        return None
    risk = abs(close - stop_mid)
    reward = abs(tgt_mid - close)
    if risk < 1e-12:
        return None
    return reward / risk


def _near_liquidity(close: float, liq_drawings: list[dict[str, Any]], bps: float = 12.0) -> bool:
    for d in liq_drawings:
        g = d.get("geometry") or {}
        if g.get("kind") != "horizontal_zone":
            continue
        try:
            lo = float(g["price_low"])
            hi = float(g["price_high"])
        except (KeyError, TypeError, ValueError):
            continue
        mid = (lo + hi) / 2.0
        if mid <= 0:
            continue
        if abs(close - mid) / mid * 10_000 <= bps:
            return True
    return False
