"""
Signalklasse: mikro | kern | gross | warnung (kontextsensitiv).
"""

from __future__ import annotations

from shared_py.signal_contracts import DecisionState, SignalClass

from signal_engine.config import SignalEngineSettings


def classify_signal(
    settings: SignalEngineSettings,
    *,
    composite_strength: float,
    decision_state: DecisionState,
    layer_flags: list[str],
    multi_tf_score: float,
    risk_score: float,
    market_regime: str | None = None,
) -> SignalClass:
    if decision_state == "rejected":
        return "warnung"
    if market_regime in ("shock", "dislocation"):
        return "warnung"
    if "recent_false_breakout" in layer_flags or "choch_churn" in layer_flags:
        return "warnung"
    if market_regime == "chop" and decision_state != "accepted":
        return "warnung"
    if decision_state == "downgraded" or multi_tf_score < 42.0:
        if composite_strength >= settings.signal_min_score_for_core and risk_score >= 50.0:
            return "kern"
        return "mikro"
    if (
        composite_strength >= settings.signal_min_score_for_gross
        and multi_tf_score >= (52.0 if market_regime == "breakout" else 58.0)
        and risk_score >= 55.0
        and decision_state == "accepted"
    ):
        return "gross"
    if market_regime == "compression" and composite_strength >= settings.signal_min_score_for_micro:
        return "mikro"
    if composite_strength >= settings.signal_min_score_for_core:
        return "kern"
    if composite_strength >= settings.signal_min_score_for_micro:
        return "mikro"
    return "warnung"
