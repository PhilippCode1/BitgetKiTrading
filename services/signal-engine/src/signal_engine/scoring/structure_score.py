"""
Schicht 1: Struktur-Score aus Trend, Swings-Kontext (State), Events (BOS/CHOCH/...).
"""

from __future__ import annotations

from typing import Any

from signal_engine.models import LayerScore, ScoringContext


def score_structure(ctx: ScoringContext) -> LayerScore:
    notes: list[str] = []
    flags: list[str] = []
    st = ctx.structure_state
    if st is None:
        return LayerScore(
            25.0,
            ["structure_state_missing"],
            ["structure_missing"],
        )

    trend = str(st.get("trend_dir", "RANGE"))
    base = 48.0
    if trend == "UP":
        base = 62.0
        notes.append("trend_up")
    elif trend == "DOWN":
        base = 62.0
        notes.append("trend_down")
    else:
        base = 44.0
        notes.append("trend_range")
        flags.append("range_regime")

    if st.get("compression_flag"):
        base += 6.0
        notes.append("compression_active")

    box = st.get("breakout_box_json")
    if isinstance(box, dict) and box.get("high") is not None:
        base += 4.0
        notes.append("breakout_box_present")

    recent_types = [str(e.get("type", "")) for e in ctx.structure_events[:12]]
    if "FALSE_BREAKOUT" in recent_types:
        base -= 22.0
        flags.append("recent_false_breakout")
        notes.append("false_breakout_recent")
    if recent_types.count("CHOCH") >= 2 and trend in ("UP", "DOWN"):
        base -= 12.0
        flags.append("choch_churn")
        notes.append("multiple_choch_noise")
    if "BOS" in recent_types and "CHOCH" in recent_types:
        # moegliche Widerspruchssituation
        base -= 6.0
        notes.append("bos_and_choch_recent")

    # Preis vs. Zonen (Drawings): Konfliktzone
    close = ctx.last_close
    if close is not None:
        in_sr = _price_in_tight_sr_zone(close, ctx.drawings)
        if in_sr:
            base -= 10.0
            flags.append("price_in_sr_conflict_zone")
            notes.append("price_inside_sr_cluster")

    score = max(0.0, min(100.0, base))
    return LayerScore(score, notes, flags)


def _price_in_tight_sr_zone(close: float, drawings: list[dict[str, Any]]) -> bool:
    for d in drawings:
        if d.get("type") not in ("support_zone", "resistance_zone"):
            continue
        g = d.get("geometry") or {}
        if g.get("kind") != "horizontal_zone":
            continue
        try:
            lo = float(g["price_low"])
            hi = float(g["price_high"])
        except (KeyError, TypeError, ValueError):
            continue
        if lo <= close <= hi and (hi - lo) / max(close, 1e-12) < 0.0025:
            return True
    return False
