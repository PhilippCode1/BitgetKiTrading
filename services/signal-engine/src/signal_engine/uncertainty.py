"""
Mehrdimensionale Unsicherheit: Modell, Daten, Regime, Execution, Policy.

Der aggregierte Score `model_uncertainty_0_1` bleibt die kanonische Kennzahl fuer
Hybrid/Leverage; er wird konservativ aus Komponenten abgeleitet (Blend + Max-Boost),
damit einzelne Risikodimensionen nicht „weggemittelt“ werden.

Policy-Version bei Semantik-Aenderung hochzaehlen.
"""

from __future__ import annotations

from typing import Any, Literal

from shared_py.signal_contracts import MetaTradeLane, TradeAction
from shared_py.uncertainty_gates import binary_normalized_entropy_0_1

from signal_engine.config import SignalEngineSettings
from signal_engine.models import ScoringContext

UNCERTAINTY_POLICY_VERSION = "uncertainty-gates-v2"

UncertaintyGatePhase = Literal["full", "minimal", "shadow_only", "blocked"]

# Gewichte fuer aggregierten Score (Summe = 1.0)
_W_DATA = 0.22
_W_REGIME = 0.20
_W_EXEC = 0.20
_W_MODEL = 0.23
_W_POLICY = 0.15
# Wenn eine Komponente dominiert, darf der Aggregate nicht kuenstlich niedrig bleiben
_MAX_COMPONENT_BOOST = 0.74


def assess_model_uncertainty(
    *,
    ctx: ScoringContext,
    settings: SignalEngineSettings,
    signal_row: dict[str, Any],
    take_trade_prediction: dict[str, Any],
    target_projection: dict[str, Any],
) -> dict[str, Any]:
    uncertainty_reasons: list[str] = []
    abstention_reasons: list[str] = []
    lane_reasons: list[str] = []

    primary = ctx.primary_feature if isinstance(ctx.primary_feature, dict) else {}

    data_issues_component = min(1.0, len(ctx.data_issues) / 4.0)
    if ctx.data_issues:
        uncertainty_reasons.extend(f"data_issue:{issue}" for issue in ctx.data_issues[:8])

    staleness_feat = _coerce_float(primary.get("staleness_score_0_1")) or 0.0
    completeness = _coerce_float(primary.get("data_completeness_0_1"))
    incompleteness = 1.0 - completeness if completeness is not None else 0.35
    incompleteness = max(0.0, min(1.0, incompleteness))
    fq = str(primary.get("feature_quality_status") or "").strip().lower()
    quality_penalty = 0.42 if fq not in {"", "ok"} else 0.0
    if quality_penalty:
        uncertainty_reasons.append("feature_quality_not_ok")

    computed_ts = primary.get("computed_ts_ms")
    analysis_ts = signal_row.get("analysis_ts_ms") or ctx.analysis_ts_ms
    age_ms: int | None = None
    stale_hard = False
    if computed_ts is not None and analysis_ts is not None:
        try:
            age_ms = int(analysis_ts) - int(computed_ts)
        except (TypeError, ValueError):
            age_ms = None
        if age_ms is not None and age_ms > int(settings.signal_max_data_age_ms):
            stale_hard = True
            uncertainty_reasons.append("feature_stale_vs_analysis_window")

    orderbook_age = _coerce_float(primary.get("orderbook_age_ms"))
    orderbook_stale = 0.0
    if orderbook_age is not None and orderbook_age > float(settings.signal_max_orderbook_age_ms):
        orderbook_stale = min(1.0, (orderbook_age - float(settings.signal_max_orderbook_age_ms)) / 30_000.0)
        uncertainty_reasons.append("orderbook_age_exec_risk")

    data_uncertainty_0_1 = min(
        1.0,
        0.38 * data_issues_component
        + 0.28 * max(staleness_feat, incompleteness * 0.85)
        + 0.22 * quality_penalty
        + 0.12 * orderbook_stale,
    )
    if stale_hard:
        data_uncertainty_0_1 = max(data_uncertainty_0_1, 0.92)

    spread_bps = _coerce_float(primary.get("spread_bps"))
    execution_cost_bps = _coerce_float(primary.get("execution_cost_bps"))
    volatility_cost_bps = _coerce_float(primary.get("volatility_cost_bps"))
    depth_ratio = _coerce_float(primary.get("depth_to_bar_volume_ratio"))
    liquidity_source = str(primary.get("liquidity_source") or "").strip().lower()

    spread_ratio = (
        spread_bps / max(float(settings.signal_max_spread_bps), 1e-9)
        if spread_bps is not None
        else 0.0
    )
    exec_combo = None
    if execution_cost_bps is not None:
        exec_combo = execution_cost_bps + (volatility_cost_bps or 0.0)
    exec_ratio = (
        exec_combo / max(float(settings.signal_max_execution_cost_bps), 1e-9)
        if exec_combo is not None
        else 0.0
    )
    depth_stress = 0.0
    if depth_ratio is not None and depth_ratio < float(settings.leverage_signal_min_depth_ratio):
        depth_stress = min(
            1.0,
            (float(settings.leverage_signal_min_depth_ratio) - depth_ratio)
            / max(float(settings.leverage_signal_min_depth_ratio), 1e-9),
        )
        uncertainty_reasons.append("execution_depth_thin")
    book_context_gap = 0.25 if liquidity_source and not liquidity_source.startswith("orderbook_levels") else 0.0

    execution_uncertainty_0_1 = min(
        1.0,
        0.42 * max(min(1.0, spread_ratio), min(1.0, exec_ratio))
        + 0.38 * depth_stress
        + 0.20 * max(orderbook_stale, book_context_gap),
    )
    if spread_ratio > 1.35 or exec_ratio > 1.25:
        uncertainty_reasons.append("execution_cost_or_spread_stress_high")

    regime_uncertainty_0_1 = _regime_uncertainty(signal_row)
    if regime_uncertainty_0_1 >= 0.45:
        uncertainty_reasons.append("regime_uncertain")

    probability = _coerce_float(take_trade_prediction.get("take_trade_prob"))
    take_trade_diag = _as_dict(take_trade_prediction.get("take_trade_model_diagnostics"))
    classifier_confidence = _coerce_float(take_trade_diag.get("confidence_0_1"))
    margin_unc = 1.0 if classifier_confidence is None else 1.0 - classifier_confidence
    entropy_uncertainty = (
        binary_normalized_entropy_0_1(probability) if probability is not None else 1.0
    )
    classifier_uncertainty = max(margin_unc, entropy_uncertainty)
    if probability is None:
        uncertainty_reasons.append("missing_take_trade_prediction")

    calibration_method = take_trade_prediction.get("take_trade_calibration_method")
    if calibration_method is None:
        calibration_method = take_trade_diag.get("calibration_method")
    if calibration_method is None:
        calibration_method = signal_row.get("take_trade_calibration_method")
    calibration_ok = True
    if settings.model_calibration_required and probability is not None:
        if not str(calibration_method or "").strip():
            calibration_ok = False
            uncertainty_reasons.append("take_trade_calibration_required_missing")

    target_diag = _as_dict(target_projection.get("target_projection_diagnostics"))
    bound_proximity = _coerce_float(target_diag.get("max_bound_proximity_0_1"))
    regressor_uncertainty = bound_proximity if bound_proximity is not None else 0.0
    missing_projection = any(
        target_projection.get(field) is None
        for field in ("expected_return_bps", "expected_mae_bps", "expected_mfe_bps")
    )
    if missing_projection:
        regressor_uncertainty = max(regressor_uncertainty, 1.0)
        uncertainty_reasons.append("missing_target_projection_output")

    shadow_divergence = _shadow_divergence(signal_row, probability)
    structural_disagreement_0_1: float
    if shadow_divergence is None:
        structural_disagreement_0_1 = 1.0
        uncertainty_reasons.append("missing_shadow_baseline")
    else:
        structural_disagreement_0_1 = min(1.0, max(0.0, shadow_divergence * 2.15))
    if shadow_divergence is not None and shadow_divergence >= settings.model_shadow_divergence_threshold:
        uncertainty_reasons.append("shadow_divergence_high")

    model_internal_0_1 = max(classifier_uncertainty, regressor_uncertainty, structural_disagreement_0_1 * 0.92)
    if model_internal_0_1 >= 0.55:
        uncertainty_reasons.append("model_confidence_low")

    ood_score = max(
        _coerce_float(take_trade_diag.get("ood_score_0_1")) or 0.0,
        _coerce_float(target_diag.get("ood_score_0_1")) or 0.0,
    )
    ood_alert = bool(take_trade_diag.get("ood_alert")) or bool(target_diag.get("ood_alert"))
    ood_reasons = _unique_strs(
        list(take_trade_diag.get("ood_reasons_json") or [])
        + list(target_diag.get("ood_reasons_json") or [])
    )
    if ood_score > 0:
        uncertainty_reasons.extend(ood_reasons[:8])

    model_uncertainty_pure = min(1.0, max(model_internal_0_1, ood_score * 0.95))

    policy_uncertainty_0_1 = 0.0
    if not calibration_ok:
        policy_uncertainty_0_1 = 1.0
    elif probability is not None:
        cm = str(calibration_method or "").strip().lower()
        if cm in {"none", "raw", "uncalibrated", "identity"}:
            policy_uncertainty_0_1 = max(policy_uncertainty_0_1, 0.52)
            uncertainty_reasons.append("take_trade_calibration_weak_method_tag")

    raw_blend = (
        _W_DATA * data_uncertainty_0_1
        + _W_REGIME * regime_uncertainty_0_1
        + _W_EXEC * execution_uncertainty_0_1
        + _W_MODEL * model_uncertainty_pure
        + _W_POLICY * policy_uncertainty_0_1
    )
    max_component = max(
        data_uncertainty_0_1,
        regime_uncertainty_0_1,
        execution_uncertainty_0_1,
        model_uncertainty_pure,
        policy_uncertainty_0_1,
    )
    uncertainty_score = min(1.0, max(raw_blend, _MAX_COMPONENT_BOOST * max_component))

    hard_abstain = False
    if stale_hard:
        hard_abstain = True
        abstention_reasons.append("feature_stale_hard_abstain")
    if not calibration_ok:
        hard_abstain = True
        abstention_reasons.append("take_trade_calibration_missing_when_required")
    if ood_alert:
        hard_abstain = True
        abstention_reasons.append("model_ood_alert")
        abstention_reasons.extend(ood_reasons[:8])
    if ood_score >= settings.model_ood_hard_abstain_score:
        hard_abstain = True
        abstention_reasons.append("ood_score_hard_abstain")
    if probability is None:
        hard_abstain = True
        abstention_reasons.append("missing_take_trade_prediction")
    if missing_projection:
        hard_abstain = True
        abstention_reasons.append("missing_target_projection_output")
    if uncertainty_score >= settings.model_max_uncertainty:
        hard_abstain = True
        abstention_reasons.append("uncertainty_above_threshold")
    if shadow_divergence is not None and shadow_divergence >= settings.model_shadow_divergence_hard_abstain:
        hard_abstain = True
        abstention_reasons.append("shadow_divergence_hard_abstain")
    if spread_ratio > 1.85 or exec_ratio > 1.75:
        hard_abstain = True
        abstention_reasons.append("execution_microstructure_hard_abstain")

    uncertainty_effective_for_leverage_0_1 = min(
        1.0,
        uncertainty_score + 0.14 * execution_uncertainty_0_1 + 0.08 * data_uncertainty_0_1,
    )

    exit_execution_bias = "normal"
    if execution_uncertainty_0_1 >= 0.58:
        exit_execution_bias = "prefer_wider_stops_and_softer_targets"
        uncertainty_reasons.append("exit_bias_widen_for_execution_uncertainty")
    elif data_uncertainty_0_1 >= 0.62:
        exit_execution_bias = "prefer_time_and_scale_out"
        uncertainty_reasons.append("exit_bias_soft_for_data_uncertainty")

    uncertainty_execution_lane: MetaTradeLane | None = None
    gate_phase: UncertaintyGatePhase = "full"

    if hard_abstain:
        gate_phase = "blocked"
        trade_action: TradeAction = "do_not_trade"
    else:
        trade_action = "allow_trade"
        want_shadow = (
            uncertainty_score >= settings.model_uncertainty_shadow_lane
            or ood_score >= settings.model_ood_shadow_lane_score
            or (shadow_divergence is not None and shadow_divergence >= settings.model_shadow_divergence_shadow_lane)
            or execution_uncertainty_0_1 >= 0.52
            or data_uncertainty_0_1 >= 0.58
        )
        want_paper = (
            uncertainty_score >= settings.model_uncertainty_paper_lane
            or ood_score >= settings.model_ood_paper_lane_score
            or execution_uncertainty_0_1 >= 0.40
        )
        if want_shadow:
            uncertainty_execution_lane = "shadow_only"
            gate_phase = "shadow_only"
            if uncertainty_score >= settings.model_uncertainty_shadow_lane:
                lane_reasons.append("uncertainty_score_shadow_lane")
            if ood_score >= settings.model_ood_shadow_lane_score:
                lane_reasons.append("ood_score_shadow_lane")
            if shadow_divergence is not None and shadow_divergence >= settings.model_shadow_divergence_shadow_lane:
                lane_reasons.append("shadow_divergence_shadow_lane")
            if execution_uncertainty_0_1 >= 0.52:
                lane_reasons.append("execution_uncertainty_shadow_lane")
            if data_uncertainty_0_1 >= 0.58:
                lane_reasons.append("data_uncertainty_shadow_lane")
        elif want_paper:
            uncertainty_execution_lane = "paper_only"
            gate_phase = "minimal"
            if uncertainty_score >= settings.model_uncertainty_paper_lane:
                lane_reasons.append("uncertainty_score_paper_lane")
            if ood_score >= settings.model_ood_paper_lane_score:
                lane_reasons.append("ood_score_paper_lane")
            if execution_uncertainty_0_1 >= 0.40:
                lane_reasons.append("execution_uncertainty_paper_lane")

    components_v2 = {
        "data_uncertainty_0_1": round(data_uncertainty_0_1, 6),
        "regime_uncertainty_0_1": round(regime_uncertainty_0_1, 6),
        "execution_uncertainty_0_1": round(execution_uncertainty_0_1, 6),
        "model_uncertainty_pure_0_1": round(model_uncertainty_pure, 6),
        "policy_uncertainty_0_1": round(policy_uncertainty_0_1, 6),
        "structural_disagreement_0_1": round(structural_disagreement_0_1, 6),
        "ood_score_0_1": round(ood_score, 6),
        "aggregate_blend_0_1": round(raw_blend, 6),
        "aggregate_with_max_boost_0_1": round(uncertainty_score, 6),
        "feature_age_ms": age_ms,
        "weights": {
            "data": _W_DATA,
            "regime": _W_REGIME,
            "execution": _W_EXEC,
            "model": _W_MODEL,
            "policy": _W_POLICY,
            "max_component_boost": _MAX_COMPONENT_BOOST,
        },
    }

    return {
        "policy_version": UNCERTAINTY_POLICY_VERSION,
        "model_uncertainty_0_1": uncertainty_score,
        "shadow_divergence_0_1": shadow_divergence if shadow_divergence is not None else 1.0,
        "model_ood_score_0_1": ood_score,
        "model_ood_alert": ood_alert,
        "data_uncertainty_0_1": data_uncertainty_0_1,
        "regime_uncertainty_0_1": regime_uncertainty_0_1,
        "execution_uncertainty_0_1": execution_uncertainty_0_1,
        "policy_uncertainty_0_1": policy_uncertainty_0_1,
        "uncertainty_effective_for_leverage_0_1": round(uncertainty_effective_for_leverage_0_1, 6),
        "uncertainty_components": components_v2,
        "uncertainty_reasons_json": _unique_strs(uncertainty_reasons),
        "ood_reasons_json": ood_reasons,
        "abstention_reasons_json": _unique_strs(abstention_reasons),
        "uncertainty_lane_reasons_json": _unique_strs(lane_reasons),
        "uncertainty_execution_lane": uncertainty_execution_lane,
        "uncertainty_gate_phase": gate_phase,
        "trade_action": trade_action,
        "exit_execution_bias": exit_execution_bias,
        "uncertainty_assessment": {
            "policy_version": UNCERTAINTY_POLICY_VERSION,
            "thresholds": {
                "model_max_uncertainty_hard": settings.model_max_uncertainty,
                "model_uncertainty_shadow_lane": settings.model_uncertainty_shadow_lane,
                "model_uncertainty_paper_lane": settings.model_uncertainty_paper_lane,
                "model_ood_hard_abstain_score": settings.model_ood_hard_abstain_score,
                "model_ood_shadow_lane_score": settings.model_ood_shadow_lane_score,
                "model_ood_paper_lane_score": settings.model_ood_paper_lane_score,
                "model_shadow_divergence_hard_abstain": settings.model_shadow_divergence_hard_abstain,
                "model_shadow_divergence_shadow_lane": settings.model_shadow_divergence_shadow_lane,
                "model_shadow_divergence_threshold": settings.model_shadow_divergence_threshold,
                "model_calibration_required": settings.model_calibration_required,
                "signal_max_data_age_ms": settings.signal_max_data_age_ms,
            },
            "components_v2": components_v2,
            "components_legacy_note": (
                "Legacy-Namen in aelteren Dashboards: model_confidence = max(classifier, regressor); "
                "structural_disagreement skaliert shadow/heuristic-Divergenz."
            ),
            "components": {
                "data_quality_issues": data_issues_component,
                "data_combined_0_1": data_uncertainty_0_1,
                "regime": regime_uncertainty_0_1,
                "execution_0_1": execution_uncertainty_0_1,
                "model_confidence": model_internal_0_1,
                "classifier_margin_uncertainty": margin_unc,
                "classifier_entropy_uncertainty_0_1": entropy_uncertainty,
                "structural_disagreement_0_1": structural_disagreement_0_1,
                "shadow_divergence_raw": shadow_divergence,
                "ood": ood_score,
            },
            "calibration": {
                "method": str(calibration_method).strip() or None,
                "required": settings.model_calibration_required,
                "ok": calibration_ok,
            },
            "take_trade_model_diagnostics": take_trade_diag,
            "target_projection_diagnostics": target_diag,
            "monitoring_hooks": {
                "false_confidence_risk": (
                    probability is not None
                    and classifier_confidence is not None
                    and classifier_confidence >= 0.82
                    and structural_disagreement_0_1 >= 0.55
                ),
                "missing_calibrator_when_required": not calibration_ok,
                "ood_fallback_only_no_alert": ood_score >= 0.55 and not ood_alert,
            },
        },
    }


def _regime_uncertainty(signal_row: dict[str, Any]) -> float:
    regime = str(signal_row.get("market_regime") or "").strip().lower()
    regime_state = str(signal_row.get("regime_state") or "").strip().lower() or regime
    transition_state = str(signal_row.get("regime_transition_state") or "").strip().lower()
    confidence = _coerce_float(signal_row.get("regime_confidence_0_1"))
    base = 0.5 if confidence is None else 1.0 - confidence
    if regime_state == "shock":
        base = max(base, 0.90)
    elif regime_state == "low_liquidity":
        base = max(base, 0.88)
    elif regime_state == "delivery_sensitive":
        base = max(base, 0.86)
    elif regime_state == "news_driven":
        base = max(base, 0.72)
    elif regime == "dislocation":
        base = max(base, 0.85)
    elif regime_state == "compression":
        base = max(base, 0.45)
    elif regime_state in {"mean_reverting", "range_grind"}:
        base = max(base, 0.42)
    elif regime == "chop":
        base = max(base, 0.35)
    if transition_state in {"entering", "sticky_hold"}:
        base = max(base, 0.55)
    return min(1.0, max(0.0, base))


def _shadow_divergence(signal_row: dict[str, Any], take_trade_prob: float | None) -> float | None:
    heuristic = _coerce_float(signal_row.get("probability_0_1"))
    if heuristic is None or take_trade_prob is None:
        return None
    return abs(heuristic - take_trade_prob)


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unique_strs(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value not in out:
            out.append(value)
    return out


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
