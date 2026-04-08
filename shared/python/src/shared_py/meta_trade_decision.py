"""
Zentrale Meta-Entscheidung: kalibrierte take_trade_prob absichern, Lane zuweisen.

Wird von der Signal-Engine Hybrid-Schicht genutzt. Deterministischer Safety-Layer
(Rejection, Uncertainty-Abstinenz) laeuft davor; diese Schicht verfeinert nur,
welche Ausfuehrungsstufe (shadow / paper / live-Kandidat) fachlich passt.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from shared_py.signal_contracts import META_TRADE_LANE_VALUES, MetaTradeLane

META_TRADE_DECISION_VERSION = "1.0.0"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class MetaTradeThresholds:
    """Schwellen (aus SignalEngineSettings)."""

    hybrid_min_take_trade_prob: float
    paper_prob_margin: float = 0.04
    paper_uncertainty_at_least: float = 0.42
    paper_execution_cost_bps_at_least: float = 15.0
    paper_risk_score_below: float = 45.0
    paper_history_score_below: float = 42.0
    paper_structure_score_below: float = 44.0
    ood_shrink_factor: float = 0.72
    uncertainty_shrink_weight: float = 0.35


def shrink_calibrated_take_trade_probability(
    p: float | None,
    *,
    ood_score_0_1: float | None,
    ood_alert: bool,
    model_uncertainty_0_1: float | None,
    ood_shrink_factor: float = 0.72,
    uncertainty_shrink_weight: float = 0.35,
) -> tuple[float | None, list[str]]:
    """
    Zieht extreme Wahrscheinlichkeiten zu 0.5, wenn OOD oder hohe Modell-Unsicherheit.
    Trainingskalibrierung bleibt im Artefakt; hier nur konservative Inferenz-Anpassung.
    """
    if p is None:
        return None, []
    reasons: list[str] = []
    t = float(p)
    if ood_alert:
        t = 0.5 + (t - 0.5) * ood_shrink_factor
        reasons.append("meta_prob_shrink_ood_alert")
    elif ood_score_0_1 is not None and ood_score_0_1 >= 0.35:
        span = max(1e-6, 1.0 - 0.35)
        f = _clamp01((float(ood_score_0_1) - 0.35) / span)
        shrink = 1.0 - f * (1.0 - ood_shrink_factor)
        t = 0.5 + (t - 0.5) * shrink
        reasons.append("meta_prob_shrink_ood_score")
    if model_uncertainty_0_1 is not None:
        u = _clamp01(float(model_uncertainty_0_1))
        if u > 0.05:
            extra = 1.0 - uncertainty_shrink_weight * u
            t = 0.5 + (t - 0.5) * extra
            reasons.append("meta_prob_shrink_uncertainty")
    return _clamp01(t), reasons


def _feature_quality_passed(source_snapshot: dict[str, Any] | None) -> bool | None:
    if not isinstance(source_snapshot, dict):
        return None
    qg = source_snapshot.get("quality_gate")
    if isinstance(qg, dict) and "passed" in qg:
        return bool(qg["passed"])
    fs = source_snapshot.get("feature_snapshot")
    if isinstance(fs, dict):
        q2 = fs.get("quality_gate")
        if isinstance(q2, dict) and "passed" in q2:
            return bool(q2["passed"])
    return None


def _primary_tf(source_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(source_snapshot, dict):
        return {}
    fs = source_snapshot.get("feature_snapshot")
    if not isinstance(fs, dict):
        return {}
    p = fs.get("primary_tf")
    return p if isinstance(p, dict) else {}


def resolve_meta_trade_lane(
    *,
    hybrid_would_allow: bool,
    safety_or_model_blocked: bool,
    take_trade_prob_adjusted: float | None,
    market_regime: str,
    model_ood_alert: bool,
    model_ood_score_0_1: float | None,
    model_uncertainty_0_1: float | None,
    risk_score_0_100: float | None,
    structure_score_0_100: float | None,
    history_score_0_100: float | None,
    source_snapshot_json: dict[str, Any] | None,
    thresholds: MetaTradeThresholds,
) -> tuple[MetaTradeLane, list[str]]:
    reasons: list[str] = []
    if safety_or_model_blocked or not hybrid_would_allow:
        reasons.append("meta_lane_hybrid_blocked")
        return "do_not_trade", reasons

    qpass = _feature_quality_passed(source_snapshot_json)
    primary = _primary_tf(source_snapshot_json)
    execution_cost_bps = _coerce_float(primary.get("execution_cost_bps"))

    stress_regime = market_regime.strip().lower() in ("shock", "dislocation")
    if stress_regime or model_ood_alert or qpass is False:
        if stress_regime:
            reasons.append("meta_lane_shadow_stress_regime")
        if model_ood_alert:
            reasons.append("meta_lane_shadow_ood_alert")
        if qpass is False:
            reasons.append("meta_lane_shadow_feature_quality")
        return "shadow_only", reasons

    paperish = False
    if take_trade_prob_adjusted is not None:
        if take_trade_prob_adjusted < thresholds.hybrid_min_take_trade_prob + thresholds.paper_prob_margin:
            reasons.append("meta_lane_paper_adjusted_prob_band")
            paperish = True
    if model_uncertainty_0_1 is not None and float(model_uncertainty_0_1) >= thresholds.paper_uncertainty_at_least:
        reasons.append("meta_lane_paper_uncertainty")
        paperish = True
    if execution_cost_bps is not None and execution_cost_bps >= thresholds.paper_execution_cost_bps_at_least:
        reasons.append("meta_lane_paper_execution_cost")
        paperish = True
    if risk_score_0_100 is not None and float(risk_score_0_100) < thresholds.paper_risk_score_below:
        reasons.append("meta_lane_paper_risk_score")
        paperish = True
    if history_score_0_100 is not None and float(history_score_0_100) < thresholds.paper_history_score_below:
        reasons.append("meta_lane_paper_history_score")
        paperish = True
    if structure_score_0_100 is not None and float(structure_score_0_100) < thresholds.paper_structure_score_below:
        reasons.append("meta_lane_paper_structure_score")
        paperish = True

    if paperish:
        return "paper_only", reasons
    reasons.append("meta_lane_live_candidate_clean")
    return "candidate_for_live", reasons


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_meta_trade_lane(value: str | None) -> Literal["valid", "invalid"]:
    if value is None or value == "":
        return "valid"
    return "valid" if value.strip().lower() in set(META_TRADE_LANE_VALUES) else "invalid"
