"""
Auswertefenster fuer Trade-Targets: keine Kerzen ausserhalb [decision_ts, closed_ts].

Wird vom Modellkern-Labeling genutzt, um Leakage durch nachtraeglich eingefuegte
oder falsch begrenzte Pfade auszuschliessen.
"""

from __future__ import annotations

from typing import Any

TARGET_EVALUATION_CONTRACT_VERSION = "1.0"


def clip_candles_to_evaluation_window(
    path_candles: list[dict[str, Any]],
    *,
    decision_ts_ms: int,
    evaluation_end_ts_ms: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Behaelt nur Kerzen mit start_ts_ms in [decision_ts_ms, evaluation_end_ts_ms].

    Kerzen strikt nach evaluation_end_ts_ms erzeugen einen Audit-Hinweis
    (Datenfehler / Leakage-Risiko), werden aber verworfen.
    """
    issues: list[str] = []
    if evaluation_end_ts_ms < decision_ts_ms:
        issues.append("evaluation_end_before_decision")
        return [], issues

    out: list[dict[str, Any]] = []
    for candle in sorted(path_candles, key=lambda c: int(c.get("start_ts_ms") or 0)):
        t = int(candle.get("start_ts_ms") or 0)
        if t < decision_ts_ms:
            continue
        if t > evaluation_end_ts_ms:
            issues.append("candle_start_after_evaluation_end")
            continue
        out.append(candle)
    return out, issues


def regime_target_stratification_hints(market_regime: str | None) -> dict[str, Any]:
    """
    Keine Umbewertung der Zahlen — reine fachliche Sichtbarkeit, wie sich
    Targets je Regime interpretieren oder stratifizieren lassen (Training/Analytics).
    """
    r = (market_regime or "").strip().lower() or "unknown"
    hints: dict[str, Any] = {
        "regime": r,
        "notes": [],
        "optional_training_strategies": [],
    }
    if r == "shock":
        hints["notes"].append(
            "Hohe Varianz in MAE/MFE erwartbar; Stratifikation oder Robust-Loss sinnvoll."
        )
        hints["optional_training_strategies"].append("regime_stratified_baseline")
    elif r == "dislocation":
        hints["notes"].append(
            "Spread-/Vol-/Funding-Stress ohne dominierendes News-Event — Execution und Slippage dominieren oft die Realisierung."
        )
        hints["optional_training_strategies"].append("liquidity_aware_labeling")
    elif r == "compression":
        hints["notes"].append(
            "Engere Range — MFE/MAE-Verhaeltnis oft anders als in Trend-Regimes."
        )
    elif r in ("trend", "breakout"):
        hints["notes"].append(
            "Trendfaehige Pfade — grosses MFE bei kleinem MAE haeufiger, Take-Trade-Label entscheidend netto."
        )
    elif r == "chop":
        hints["notes"].append(
            "Whipsaw-Risiko — MAE relativ zu MFE oft hoeher; Liquidationsnaehe separat beobachten."
        )
    else:
        hints["notes"].append("Regime unbekannt oder gemischt — konservative Interpretation.")
    return hints
