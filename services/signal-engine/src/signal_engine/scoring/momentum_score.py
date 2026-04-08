"""
Schicht 2: Momentum aus Feature-Row (Primary TF) + Abgleich Strukturrichtung.
"""

from __future__ import annotations

import math

from signal_engine.models import LayerScore, ScoringContext


def score_momentum(ctx: ScoringContext) -> LayerScore:
    notes: list[str] = []
    flags: list[str] = []
    f = ctx.primary_feature
    if f is None:
        return LayerScore(30.0, ["primary_feature_missing"], ["feature_missing"])

    st = ctx.structure_state
    trend = str(st.get("trend_dir", "RANGE")) if st is not None else "RANGE"

    base = 50.0
    mom = f.get("momentum_score")
    if mom is not None and not (isinstance(mom, float) and math.isnan(mom)):
        base = float(mom)
        notes.append("used_feature_momentum_score")

    rsi = f.get("rsi_14")
    if rsi is not None:
        r = float(rsi)
        if r > 72:
            base -= 8.0
            flags.append("rsi_overbought")
            notes.append("rsi_high")
        elif r < 28:
            base -= 8.0
            flags.append("rsi_oversold")
            notes.append("rsi_low")
        else:
            notes.append("rsi_mid_zone")

    ret1 = f.get("ret_1")
    if ret1 is not None:
        r1 = float(ret1)
        if trend == "UP" and r1 < -0.0008:
            base -= 12.0
            flags.append("momentum_vs_structure_up")
            notes.append("negative_ret1_vs_uptrend")
        elif trend == "DOWN" and r1 > 0.0008:
            base -= 12.0
            flags.append("momentum_vs_structure_down")
            notes.append("positive_ret1_vs_downtrend")

    body = f.get("impulse_body_ratio")
    if body is not None:
        b = float(body)
        if b > 0.55:
            base += 6.0
            notes.append("strong_body_impulse")
        elif b < 0.25:
            base -= 5.0
            notes.append("weak_body_doji_like")

    volz = f.get("vol_z_50")
    if volz is not None:
        vz = abs(float(volz))
        if vz > 2.5:
            base -= 5.0
            flags.append("volume_anomaly")
            notes.append("vol_z_extreme")

    imbalance = f.get("orderbook_imbalance")
    if imbalance is not None:
        imb = float(imbalance)
        if trend == "UP" and imb > 0.15:
            base += 5.0
            notes.append("orderbook_bid_pressure_supports_uptrend")
        elif trend == "UP" and imb < -0.15:
            base -= 7.0
            flags.append("orderbook_vs_structure_up")
            notes.append("orderbook_ask_pressure_against_uptrend")
        elif trend == "DOWN" and imb < -0.15:
            base += 5.0
            notes.append("orderbook_ask_pressure_supports_downtrend")
        elif trend == "DOWN" and imb > 0.15:
            base -= 7.0
            flags.append("orderbook_vs_structure_down")
            notes.append("orderbook_bid_pressure_against_downtrend")

    score = max(0.0, min(100.0, base))
    return LayerScore(score, notes, flags)
