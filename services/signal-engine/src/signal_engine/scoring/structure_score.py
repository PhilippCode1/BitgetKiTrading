"""
Schicht 1: Struktur-Score aus Trend, Swings-Kontext (State), Events (BOS/CHOCH/...).
"""

from __future__ import annotations

from typing import Any

from signal_engine.models import LayerScore, ScoringContext


def _f(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> int | None:
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def compute_grid_boundaries(
    candles: list[dict[str, Any]] | None,
    zones: list[dict[str, Any]] | dict[str, Any] | None,
) -> tuple[float, float, int]:
    """
    Berechnet die Gitter-Grenzen (upper_bound, lower_bound) knapp ober-/unterhalb der primären
    Support-/Resistance-Cluster und bestimmt die Grid-Anzahl dynamisch auf Basis der ATR.
    """
    support_prices: list[float] = []
    resistance_prices: list[float] = []

    drawings_list: list[dict[str, Any]] = []
    if isinstance(zones, list):
        drawings_list = zones
    elif isinstance(zones, dict):
        drawings_list = zones.get("drawings", []) or zones.get("zones", []) or []
        if not isinstance(drawings_list, list):
            drawings_list = []

    # Extrahiere Support- und Resistance-Level aus drawings
    for d in drawings_list:
        dtype = str(d.get("type", "")).lower()
        g = d.get("geometry") or {}
        if "support" in dtype or "demand" in dtype:
            for key in ("price_low", "price_high", "price", "level"):
                if key in g:
                    v = _f(g[key])
                    if v is not None:
                        support_prices.append(v)
        elif "resistance" in dtype or "supply" in dtype:
            for key in ("price_low", "price_high", "price", "level"):
                if key in g:
                    v = _f(g[key])
                    if v is not None:
                        resistance_prices.append(v)

    # Kerzen-Preise extrahieren falls vorhanden
    close_prices: list[float] = []
    high_prices: list[float] = []
    low_prices: list[float] = []
    
    candles_list = candles or []
    for c in candles_list:
        try:
            close_prices.append(float(c.get("close", 0)))
            high_prices.append(float(c.get("high", 0)))
            low_prices.append(float(c.get("low", 0)))
        except (TypeError, ValueError):
            pass

    last_close = close_prices[-1] if close_prices else 50000.0

    # Bestimmung der primären Support- und Resistance-Level
    if support_prices:
        primary_support = min(support_prices)
    else:
        primary_support = min(low_prices) if low_prices else last_close * 0.95

    if resistance_prices:
        primary_resistance = max(resistance_prices)
    else:
        primary_resistance = max(high_prices) if high_prices else last_close * 1.05

    # Die lower_bound muss knapp unter dem primären Support-Cluster angesetzt werden,
    # die upper_bound knapp über dem primären Resistance-Cluster.
    lower_bound = round(primary_support * 0.985, 2)
    upper_bound = round(primary_resistance * 1.015, 2)

    if upper_bound <= lower_bound:
        upper_bound = round(last_close * 1.05, 2)
        lower_bound = round(last_close * 0.95, 2)

    # ATR (Average True Range) berechnen (Standardmäßig 1% Fallback)
    atr = last_close * 0.01
    if len(candles_list) >= 2:
        trs = []
        for i in range(1, len(candles_list)):
            try:
                h = float(candles_list[i].get("high", 0))
                l = float(candles_list[i].get("low", 0))
                pc = float(candles_list[i-1].get("close", 0))
                tr = max(h - l, abs(h - pc), abs(l - pc))
                trs.append(tr)
            except (TypeError, ValueError):
                pass
        if trs:
            atr = sum(trs[-14:]) / len(trs[-14:])

    # Je enger der Markt (kleine ATR), desto dichter das Gitternetz (höhere Grid-Anzahl),
    # gedeckelt auf ein konfigurierbares Maximum (z.B. 50).
    atr_pct = atr / max(last_close, 1e-12)
    if atr_pct <= 0.0:
        atr_pct = 0.01

    raw_count = int(0.2 / atr_pct)
    grid_count = max(5, min(50, raw_count))

    return lower_bound, upper_bound, grid_count


def score_structure(ctx: ScoringContext) -> LayerScore:
    notes: list[str] = []
    flags: list[str] = []
    st = ctx.structure_state
    
    # Sicherstellen, dass structure_state ein Dictionary ist zur sicheren Mutation
    if st is None:
        ctx.structure_state = {}
        st = ctx.structure_state
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

    # --- Trend-Stärke & Grid-Grenzen dynamisch ermitteln ---
    trend_strength = _f(st.get("trend_strength_0_1"))
    if trend_strength is None:
        trend_strength = _f(st.get("trend_strength"))
    if trend_strength is None:
        # Heuristische Berechnung basierend auf Trend & Events
        if trend in ("UP", "DOWN"):
            trend_strength = 0.55
            if "BOS" in recent_types:
                trend_strength += 0.15
        else:
            trend_strength = 0.25

    trend_breakout_detected = False
    if trend_strength > 0.65:
        trend_breakout_detected = True
        flags.append("trend_breakout_detected")
        notes.append("trend_breakout_veto_active")

    # Gitter-Parameter berechnen
    candles_history: list[dict[str, Any]] = []
    # Versuche Candles aus features_by_tf oder primary_feature zu extrahieren, falls vorhanden
    if ctx.primary_feature and isinstance(ctx.primary_feature, dict):
        # Falls das feature-dict candle-aehnliche Infos hat
        candles_history.append(ctx.primary_feature)

    lower_bound, upper_bound, grid_count = compute_grid_boundaries(candles_history, ctx.drawings)

    # Bot-Faehigkeit des Instruments pruefen
    bot_supported = False
    if ctx.instrument_execution_meta and isinstance(ctx.instrument_execution_meta, dict):
        bot_supported = bool(ctx.instrument_execution_meta.get("bot_trading_supported", False))
    if not bot_supported and isinstance(ctx.structure_state, dict):
        bot_supported = bool(ctx.structure_state.get("bot_trading_supported", False))

    # Mutate structure_state so it is forwarded to service.py and MDK
    st["bot_trading_supported"] = bot_supported
    st["grid_lower_bound"] = lower_bound
    st["grid_upper_bound"] = upper_bound
    st["grid_count"] = grid_count
    st["trend_breakout_detected"] = trend_breakout_detected
    st["trend_strength_0_1"] = trend_strength

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
