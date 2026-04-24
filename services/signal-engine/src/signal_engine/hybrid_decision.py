from __future__ import annotations

from typing import Any

from shared_py.leverage_allocator import LEVERAGE_ALLOCATOR_VERSION, allocate_integer_leverage
from shared_py.unified_leverage_allocator import recompute_unified_leverage_allocation
from shared_py.projection_adjustment import (
    cap_from_liquidation_stress,
    liquidation_proximity_stress_0_1,
)
from shared_py.meta_trade_decision import (
    META_TRADE_DECISION_VERSION,
    MetaTradeThresholds,
    resolve_meta_trade_lane,
    shrink_calibrated_take_trade_probability,
)
from shared_py.signal_contracts import DecisionState, TradeAction

from signal_engine.config import SignalEngineSettings
from signal_engine.product_family_risk import (
    effective_min_leverage,
    market_family_from_signal_row,
    max_config_risk_leverage,
)
from signal_engine.risk_governor import (
    apply_live_ramp_cap,
    assess_risk_governor,
    extract_risk_account_snapshot,
)

HYBRID_DECISION_POLICY_VERSION = "hybrid-v5"


def assess_hybrid_decision(
    *,
    settings: SignalEngineSettings,
    signal_row: dict[str, Any],
) -> dict[str, Any]:
    direction = str(signal_row.get("direction") or "").strip().lower()
    product_family = market_family_from_signal_row(signal_row)
    gov = assess_risk_governor(settings=settings, signal_row=signal_row, direction=direction)
    governor_hard: list[str] = []
    if getattr(settings, "risk_hard_gating_enabled", True):
        governor_hard = list(gov.get("hard_block_reasons_json") or [])

    signal_class = str(signal_row.get("signal_class") or "").strip().lower() or "warnung"
    market_regime = str(signal_row.get("market_regime") or "").strip().lower()
    regime_bias = str(signal_row.get("regime_bias") or "").strip().lower()
    regime_confidence = _clamp01(_coerce_float(signal_row.get("regime_confidence_0_1")) or 0.0)
    take_trade_prob = _coerce_float(signal_row.get("take_trade_prob"))
    take_trade_prob_adjusted, prob_shrink_reasons = shrink_calibrated_take_trade_probability(
        take_trade_prob,
        ood_score_0_1=_coerce_float(signal_row.get("model_ood_score_0_1")),
        ood_alert=bool(signal_row.get("model_ood_alert")),
        model_uncertainty_0_1=_coerce_float(signal_row.get("model_uncertainty_0_1")),
        ood_shrink_factor=settings.meta_prob_ood_shrink_factor,
        uncertainty_shrink_weight=settings.meta_prob_uncertainty_shrink_weight,
    )
    heuristic_probability = _coerce_float(signal_row.get("probability_0_1"))
    expected_return_bps = _coerce_float(signal_row.get("expected_return_bps"))
    expected_mae_bps = _coerce_float(signal_row.get("expected_mae_bps"))
    expected_mfe_bps = _coerce_float(signal_row.get("expected_mfe_bps"))
    signal_strength = _clamp01((_coerce_float(signal_row.get("signal_strength_0_100")) or 0.0) / 100.0)
    composite_strength = _clamp01(
        (_coerce_float(signal_row.get("weighted_composite_score_0_100")) or 0.0) / 100.0
    )
    model_uncertainty = _clamp01(_coerce_float(signal_row.get("model_uncertainty_0_1")) or 1.0)
    uncertainty_component = 1.0 - model_uncertainty
    projected_rr = _projected_rr(expected_mae_bps, expected_mfe_bps)
    regime_alignment = _regime_alignment(
        direction=direction,
        regime_bias=regime_bias,
        regime_confidence=regime_confidence,
    )
    trade_score = _trade_score(
        signal_strength=signal_strength,
        composite_strength=composite_strength,
        take_trade_prob=take_trade_prob_adjusted,
        heuristic_probability=heuristic_probability,
        expected_return_bps=expected_return_bps,
        projected_rr=projected_rr,
        regime_alignment=regime_alignment,
        uncertainty_component=uncertainty_component,
        min_expected_return_bps=settings.hybrid_decision_min_expected_return_bps,
        min_projected_rr=settings.hybrid_decision_min_projected_rr,
    )

    safety_floor_reasons = _safety_floor_reasons(signal_row)
    if governor_hard:
        safety_floor_reasons = _unique_strs(safety_floor_reasons + governor_hard)
    model_gate_reasons = (
        []
        if safety_floor_reasons
        else _model_gate_reasons(
            settings=settings,
            direction=direction,
            market_regime=market_regime,
            regime_bias=regime_bias,
            regime_confidence=regime_confidence,
            take_trade_prob=take_trade_prob_adjusted,
            expected_return_bps=expected_return_bps,
            expected_mae_bps=expected_mae_bps,
            projected_rr=projected_rr,
        )
    )

    if safety_floor_reasons:
        final_decision_state: DecisionState = "rejected"
        final_trade_action: TradeAction = "do_not_trade"
        decision_confidence = max(0.75, 1.0 - (model_uncertainty * 0.35))
    elif model_gate_reasons:
        final_decision_state = "downgraded"
        final_trade_action = "do_not_trade"
        decision_confidence = max(0.55, 1.0 - trade_score)
    else:
        final_decision_state = "accepted"
        final_trade_action = "allow_trade"
        decision_confidence = max(0.55, trade_score)

    lev_eff = _coerce_float(signal_row.get("uncertainty_effective_for_leverage_0_1"))
    model_uncertainty_for_leverage = (
        _clamp01(max(model_uncertainty, float(lev_eff))) if lev_eff is not None else model_uncertainty
    )
    leverage_decision = _signal_leverage_decision(
        settings=settings,
        signal_row=signal_row,
        direction=direction,
        projected_rr=projected_rr,
        expected_return_bps=expected_return_bps,
        expected_mae_bps=expected_mae_bps,
        decision_confidence=decision_confidence,
        trade_score=trade_score,
        model_uncertainty=model_uncertainty_for_leverage,
        governor_max_leverage=int(gov["max_leverage_cap"]),
        market_family=product_family,
    )
    leverage_block_reason = leverage_decision["blocked_reason"]
    min_lev = effective_min_leverage(product_family, settings.risk_allowed_leverage_min)
    if final_trade_action == "allow_trade" and leverage_decision["allowed_leverage"] < min_lev:
        final_decision_state = "downgraded"
        final_trade_action = "do_not_trade"
        model_gate_reasons = _unique_strs(
            model_gate_reasons
            + ["hybrid_allowed_leverage_below_minimum"]
            + list(leverage_decision.get("cap_reasons_json") or [])
        )
        decision_confidence = min(decision_confidence, 0.74)

    safety_or_model_blocked = bool(safety_floor_reasons or model_gate_reasons)
    hybrid_allow = final_trade_action == "allow_trade"
    source_snap = signal_row.get("source_snapshot_json")
    source_snap_dict = source_snap if isinstance(source_snap, dict) else None
    meta_thresholds = MetaTradeThresholds(
        hybrid_min_take_trade_prob=settings.hybrid_decision_min_take_trade_prob,
        paper_prob_margin=settings.meta_lane_paper_prob_margin,
        paper_uncertainty_at_least=settings.meta_lane_paper_uncertainty_at_least,
        paper_execution_cost_bps_at_least=settings.meta_lane_paper_execution_cost_bps_at_least,
        paper_risk_score_below=settings.meta_lane_paper_risk_score_below,
        paper_history_score_below=settings.meta_lane_paper_history_score_below,
        paper_structure_score_below=settings.meta_lane_paper_structure_score_below,
        ood_shrink_factor=settings.meta_prob_ood_shrink_factor,
        uncertainty_shrink_weight=settings.meta_prob_uncertainty_shrink_weight,
    )
    meta_lane, meta_lane_reasons = resolve_meta_trade_lane(
        hybrid_would_allow=hybrid_allow,
        safety_or_model_blocked=safety_or_model_blocked,
        take_trade_prob_adjusted=take_trade_prob_adjusted,
        market_regime=market_regime,
        model_ood_alert=bool(signal_row.get("model_ood_alert")),
        model_ood_score_0_1=_coerce_float(signal_row.get("model_ood_score_0_1")),
        model_uncertainty_0_1=_coerce_float(signal_row.get("model_uncertainty_0_1")),
        risk_score_0_100=_coerce_float(signal_row.get("risk_score_0_100")),
        structure_score_0_100=_coerce_float(signal_row.get("structure_score_0_100")),
        history_score_0_100=_coerce_float(signal_row.get("history_score_0_100")),
        source_snapshot_json=source_snap_dict,
        thresholds=meta_thresholds,
    )
    meta_lane_extra: list[str] = []
    if meta_lane == "shadow_only" and final_trade_action == "allow_trade":
        final_trade_action = "do_not_trade"
        final_decision_state = "downgraded"
        meta_lane_extra.append("meta_lane_shadow_blocks_execution")

    final_allowed = int(leverage_decision["allowed_leverage"])
    final_rec = (
        leverage_decision["recommended_leverage"]
        if final_trade_action == "allow_trade"
        else None
    )
    if final_trade_action == "allow_trade":
        final_allowed, final_rec = apply_live_ramp_cap(
            settings=settings,
            meta_trade_lane=meta_lane,
            allowed_leverage=final_allowed,
            recommended_leverage=final_rec,
            signal_row=signal_row,
            governor=gov,
        )
    leverage_decision = {**leverage_decision, "allowed_leverage": final_allowed}
    leverage_decision["recommended_leverage"] = final_rec

    acct_snap = extract_risk_account_snapshot(_as_dict(signal_row.get("source_snapshot_json")))
    stop_proxy_pct: float | None = None
    if expected_mae_bps is not None and float(expected_mae_bps) > 0:
        stop_proxy_pct = float(expected_mae_bps) / 10000.0
    leverage_decision["unified_leverage_allocation"] = recompute_unified_leverage_allocation(
        allowed_leverage=int(final_allowed),
        recommended_leverage=final_rec,
        stop_distance_pct=stop_proxy_pct,
        meta_trade_lane=meta_lane,
        trade_action=final_trade_action,
        governor=gov,
        risk_account_snapshot=acct_snap,
        signal_row=signal_row,
        settings=settings,
    )

    abstention_reasons = _unique_strs(
        list(signal_row.get("abstention_reasons_json") or [])
        + safety_floor_reasons
        + model_gate_reasons
        + (
            [leverage_block_reason]
            if final_trade_action == "do_not_trade" and leverage_block_reason
            else []
        )
        + meta_lane_reasons
        + meta_lane_extra
    )

    approval_reasons = []
    if final_trade_action == "allow_trade":
        approval_reasons = [
            "hybrid_safety_floor_passed",
            "hybrid_take_trade_prob_ok",
            "hybrid_expected_return_ok",
            "hybrid_projected_rr_ok",
            "hybrid_allowed_leverage_ok",
        ]
        if expected_mae_bps is not None:
            approval_reasons.append("hybrid_expected_mae_ok")
        if regime_bias in ("neutral", direction):
            approval_reasons.append("hybrid_regime_aligned")
        approval_reasons.append(f"meta_trade_lane_{meta_lane}")

    final_signal_class = signal_class if final_trade_action == "allow_trade" else "warnung"
    leverage_cap_reasons = _unique_strs(
        list(leverage_decision["cap_reasons_json"]) + list(leverage_decision["factor_reasons_json"])
    )
    _u = leverage_decision.get("unified_leverage_allocation") or {}
    return {
        "decision_policy_version": HYBRID_DECISION_POLICY_VERSION,
        "market_family": product_family,
        "decision_confidence_0_1": round(_clamp01(decision_confidence), 6),
        "allowed_leverage": leverage_decision["allowed_leverage"],
        "recommended_leverage": (
            leverage_decision["recommended_leverage"] if final_trade_action == "allow_trade" else None
        ),
        "execution_leverage_cap": _u.get("execution_leverage_cap"),
        "mirror_leverage": _u.get("mirror_leverage"),
        "unified_leverage_allocator_version": _u.get("version"),
        "live_execution_block_reasons_json": list(gov.get("live_execution_block_reasons_json") or []),
        "portfolio_risk_synthesis_json": gov.get("portfolio_risk_synthesis_json"),
        "leverage_policy_version": LEVERAGE_ALLOCATOR_VERSION,
        "leverage_cap_reasons_json": leverage_cap_reasons,
        "decision_state": final_decision_state,
        "trade_action": final_trade_action,
        "meta_trade_lane": meta_lane,
        "signal_class": final_signal_class,
        "abstention_reasons_json": abstention_reasons,
        "hybrid_decision": {
            "policy_version": HYBRID_DECISION_POLICY_VERSION,
            "trade_action": final_trade_action,
            "meta_trade_decision_version": META_TRADE_DECISION_VERSION,
            "meta_trade_lane": meta_lane,
            "meta_lane_reasons": list(dict.fromkeys(meta_lane_reasons + meta_lane_extra)),
            "take_trade_prob_adjusted_0_1": take_trade_prob_adjusted,
            "take_trade_prob_raw_0_1": take_trade_prob,
            "prob_shrink_reasons": prob_shrink_reasons,
            "decision_state": final_decision_state,
            "direction": direction or None,
            "confidence_0_1": round(_clamp01(decision_confidence), 6),
            "trade_score_0_1": round(trade_score, 6),
            "expected_edge_bps": expected_return_bps,
            "expected_mae_bps": expected_mae_bps,
            "expected_mfe_bps": expected_mfe_bps,
            "projected_reward_to_adverse_ratio": projected_rr,
            "uncertainty_0_1": model_uncertainty,
            "allowed_leverage": leverage_decision["allowed_leverage"],
            "recommended_leverage": (
                leverage_decision["recommended_leverage"] if final_trade_action == "allow_trade" else None
            ),
            "leverage_policy_version": LEVERAGE_ALLOCATOR_VERSION,
            "leverage_allocator": leverage_decision,
            "risk_governor": gov,
            "live_execution_block_reasons_json": list(gov.get("live_execution_block_reasons_json") or []),
            "governor_universal_hard_block_reasons_json": list(
                gov.get("universal_hard_block_reasons_json") or []
            ),
            "primary_abstention_reason": abstention_reasons[0] if abstention_reasons else None,
            "safety_floor_reasons": safety_floor_reasons,
            "model_gate_reasons": model_gate_reasons,
            "approval_reasons": approval_reasons,
            "inputs": {
                "market_family": product_family,
                "market_regime": market_regime or None,
                "regime_bias": regime_bias or None,
                "regime_confidence_0_1": regime_confidence,
                "signal_strength_0_1": signal_strength,
                "weighted_composite_0_1": composite_strength,
                "take_trade_prob": take_trade_prob,
                "take_trade_prob_adjusted_0_1": take_trade_prob_adjusted,
                "heuristic_probability_0_1": heuristic_probability,
                "expected_return_bps": expected_return_bps,
                "expected_mae_bps": expected_mae_bps,
                "expected_mfe_bps": expected_mfe_bps,
                "model_uncertainty_0_1": model_uncertainty,
                "liquidation_proximity_stress_0_1": (
                    (leverage_decision.get("market_inputs") or {}).get(
                        "liquidation_proximity_stress_0_1"
                    )
                ),
            },
        },
    }


def _safety_floor_reasons(signal_row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    direction = str(signal_row.get("direction") or "").strip().lower()
    if direction not in {"long", "short"}:
        reasons.append("hybrid_direction_not_tradable")
    if bool(signal_row.get("rejection_state")):
        reasons.append("hybrid_rejection_state_active")
    decision_state = str(signal_row.get("decision_state") or "").strip().lower()
    if decision_state != "accepted":
        reasons.append("hybrid_safety_floor_not_accepted")
    trade_action = str(signal_row.get("trade_action") or "").strip().lower()
    if trade_action == "do_not_trade":
        reasons.append("hybrid_prior_do_not_trade")
    signal_class = str(signal_row.get("signal_class") or "").strip().lower()
    if signal_class == "warnung":
        reasons.append("hybrid_warning_signal_class")
    return _unique_strs(reasons)


def _model_gate_reasons(
    *,
    settings: SignalEngineSettings,
    direction: str,
    market_regime: str,
    regime_bias: str,
    regime_confidence: float,
    take_trade_prob: float | None,
    expected_return_bps: float | None,
    expected_mae_bps: float | None,
    projected_rr: float | None,
) -> list[str]:
    reasons: list[str] = []
    if direction not in {"long", "short"}:
        reasons.append("hybrid_direction_not_tradable")
    if take_trade_prob is None:
        reasons.append("hybrid_missing_take_trade_prob")
    elif take_trade_prob < settings.hybrid_decision_min_take_trade_prob:
        reasons.append("hybrid_take_trade_prob_below_minimum")
    if expected_return_bps is None:
        reasons.append("hybrid_missing_expected_return_bps")
    elif expected_return_bps < settings.hybrid_decision_min_expected_return_bps:
        reasons.append("hybrid_expected_return_below_minimum")
    if expected_mae_bps is None:
        reasons.append("hybrid_missing_expected_mae_bps")
    elif expected_mae_bps > settings.hybrid_decision_max_expected_mae_bps:
        reasons.append("hybrid_expected_mae_above_maximum")
    if projected_rr is None:
        reasons.append("hybrid_missing_projected_rr")
    elif projected_rr < settings.hybrid_decision_min_projected_rr:
        reasons.append("hybrid_projected_rr_below_minimum")
    if (
        market_regime
        and regime_bias in {"long", "short"}
        and regime_bias != direction
        and regime_confidence >= settings.hybrid_decision_regime_conflict_threshold
    ):
        reasons.append("hybrid_regime_bias_conflict")
    return _unique_strs(reasons)


def _trade_score(
    *,
    signal_strength: float,
    composite_strength: float,
    take_trade_prob: float | None,
    heuristic_probability: float | None,
    expected_return_bps: float | None,
    projected_rr: float | None,
    regime_alignment: float,
    uncertainty_component: float,
    min_expected_return_bps: float,
    min_projected_rr: float,
) -> float:
    probability_component = _clamp01(
        take_trade_prob if take_trade_prob is not None else (heuristic_probability or 0.0)
    )
    edge_component = 0.0
    if expected_return_bps is not None and min_expected_return_bps > 0:
        edge_component = _clamp01(expected_return_bps / max(min_expected_return_bps * 2.0, 1.0))
    rr_component = 0.0
    if projected_rr is not None and min_projected_rr > 0:
        rr_component = _clamp01(projected_rr / max(min_projected_rr * 1.5, 1.0))
    score = (
        0.18 * signal_strength
        + 0.17 * composite_strength
        + 0.24 * probability_component
        + 0.18 * edge_component
        + 0.11 * rr_component
        + 0.07 * regime_alignment
        + 0.05 * uncertainty_component
    )
    return round(_clamp01(score), 6)


def _signal_leverage_decision(
    *,
    settings: SignalEngineSettings,
    signal_row: dict[str, Any],
    direction: str,
    projected_rr: float | None,
    expected_return_bps: float | None,
    expected_mae_bps: float | None,
    decision_confidence: float,
    trade_score: float,
    model_uncertainty: float,
    governor_max_leverage: int,
    market_family: str = "futures",
) -> dict[str, Any]:
    source_snapshot = _as_dict(signal_row.get("source_snapshot_json"))
    feature_snapshot = _as_dict(source_snapshot.get("feature_snapshot"))
    quality_gate = _as_dict(source_snapshot.get("quality_gate"))
    instrument_meta = _as_dict(source_snapshot.get("instrument"))
    primary_tf = _as_dict(feature_snapshot.get("primary_tf"))
    data_issues = _unique_strs(
        list(source_snapshot.get("data_issues") or []) + list(signal_row.get("uncertainty_reasons_json") or [])
    )
    config_hi = min(settings.risk_allowed_leverage_max, 75)
    risk_max = max_config_risk_leverage(
        market_family,
        max(settings.risk_allowed_leverage_min, config_hi),
    )
    eff_min = effective_min_leverage(market_family, settings.risk_allowed_leverage_min)
    liq_preview = 1 if market_family == "spot" else risk_max
    liq_stress = liquidation_proximity_stress_0_1(
        effective_adverse_bps=expected_mae_bps,
        preview_leverage=liq_preview,
    )
    liq_cap_val = cap_from_liquidation_stress(stress_0_1=liq_stress, risk_max=max(1, risk_max))
    if liq_cap_val is None:
        liq_cap_val = risk_max

    expected_volatility_band = _coerce_float(signal_row.get("expected_volatility_band"))
    if expected_volatility_band is None:
        expected_volatility_band = _coerce_float(primary_tf.get("atrp_14"))
    spread_bps = _coerce_float(primary_tf.get("spread_bps"))
    execution_cost_bps = _coerce_float(primary_tf.get("execution_cost_bps"))
    volatility_cost_bps = _coerce_float(primary_tf.get("volatility_cost_bps"))
    funding_rate_bps = abs(_coerce_float(primary_tf.get("funding_rate_bps")) or 0.0)
    funding_window_bps = abs(_coerce_float(primary_tf.get("funding_cost_bps_window")) or 0.0)
    depth_ratio = _coerce_float(primary_tf.get("depth_to_bar_volume_ratio"))
    liquidity_source = str(primary_tf.get("liquidity_source") or "").strip().lower()
    if direction == "short":
        impact_bps = _coerce_float(primary_tf.get("impact_sell_bps_10000"))
    else:
        impact_bps = _coerce_float(primary_tf.get("impact_buy_bps_10000"))

    gov_bind_floor = 1 if market_family == "spot" else 7
    risk_gov_cap = max(
        gov_bind_floor,
        min(75, int(governor_max_leverage)),
    )
    factor_caps = {
        "edge_factor_cap": _cap_from_score(
            _edge_score(
                expected_return_bps=expected_return_bps,
                projected_rr=projected_rr,
                decision_confidence=decision_confidence,
                trade_score=trade_score,
                min_expected_return_bps=settings.hybrid_decision_min_expected_return_bps,
                min_projected_rr=settings.hybrid_decision_min_projected_rr,
            ),
            risk_max=risk_max,
        ),
        "uncertainty_factor_cap": _cap_from_score(
            max(0.0, 1.0 - model_uncertainty),
            risk_max=risk_max,
        ),
        "volatility_factor_cap": _cap_from_score(
            _cost_score(
                value=expected_volatility_band,
                hard_limit=settings.leverage_signal_max_volatility_band,
                scale=1.0,
            ),
            risk_max=risk_max,
        ),
        "spread_factor_cap": _cap_from_score(
            _cost_score(
                value=spread_bps,
                hard_limit=settings.signal_max_spread_bps,
                scale=1.2,
            ),
            risk_max=risk_max,
        ),
        "slippage_factor_cap": _cap_from_score(
            _cost_score(
                value=(execution_cost_bps or 0.0) + (volatility_cost_bps or 0.0),
                hard_limit=max(settings.signal_max_execution_cost_bps * 2.0, 1.0),
                scale=1.0,
            ),
            risk_max=risk_max,
        ),
        "funding_factor_cap": _cap_from_score(
            _cost_score(
                value=max(funding_rate_bps, funding_window_bps),
                hard_limit=max(settings.signal_max_adverse_funding_bps * 2.0, 1.0),
                scale=1.0,
            ),
            risk_max=risk_max,
        ),
        "depth_factor_cap": _cap_from_score(
            _depth_score(
                depth_ratio=depth_ratio,
                impact_bps=impact_bps,
                min_depth_ratio=settings.leverage_signal_min_depth_ratio,
                max_impact_bps=settings.leverage_signal_max_impact_bps_10000,
                liquidity_source=liquidity_source,
            ),
            risk_max=risk_max,
        ),
        "liquidation_proximity_cap": liq_cap_val,
        "data_quality_factor_cap": 6
        if data_issues or quality_gate.get("passed") is False
        else risk_max,
        "risk_governor_cap": min(risk_max, risk_gov_cap),
        "instrument_metadata_cap": (
            risk_max
            if market_family == "spot"
            else (
                max(
                    0,
                    min(
                        risk_max,
                        int(instrument_meta.get("leverage_max")),
                    ),
                )
                if instrument_meta.get("supports_leverage") is True
                and instrument_meta.get("leverage_max") not in (None, "")
                else (
                    0
                    if instrument_meta.get("supports_leverage") is False
                    else risk_max
                )
            )
        ),
    }
    model_cap = min(factor_caps.values()) if factor_caps else risk_max
    decision = allocate_integer_leverage(
        requested_leverage=risk_max,
        caps={"model_cap": model_cap},
        min_leverage=eff_min,
        max_leverage=risk_max,
        blocked_reason="hybrid_allowed_leverage_below_minimum",
    )
    factor_reasons = sorted(
        [name for name, value in factor_caps.items() if value == model_cap]
    )
    decision["factor_caps"] = factor_caps
    decision["factor_reasons_json"] = factor_reasons
    decision["quality_gate_passed"] = quality_gate.get("passed", True)
    decision["data_issues"] = data_issues
    decision["market_inputs"] = {
        "expected_volatility_band": expected_volatility_band,
        "spread_bps": spread_bps,
        "execution_cost_bps": execution_cost_bps,
        "volatility_cost_bps": volatility_cost_bps,
        "funding_rate_bps": funding_rate_bps,
        "funding_cost_bps_window": funding_window_bps,
        "depth_to_bar_volume_ratio": depth_ratio,
        "impact_bps_10000": impact_bps,
        "liquidity_source": liquidity_source or None,
        "liquidation_proximity_stress_0_1": liq_stress,
        "liquidation_preview_leverage": liq_preview,
    }
    return decision


def _regime_alignment(
    *,
    direction: str,
    regime_bias: str,
    regime_confidence: float,
) -> float:
    if direction not in {"long", "short"}:
        return 0.0
    if regime_bias in {"", "neutral"}:
        return 0.55
    if regime_bias == direction:
        return _clamp01(0.5 + (regime_confidence * 0.5))
    return _clamp01(0.35 * (1.0 - regime_confidence))


def _projected_rr(expected_mae_bps: float | None, expected_mfe_bps: float | None) -> float | None:
    if expected_mae_bps is None or expected_mfe_bps is None:
        return None
    if expected_mae_bps <= 0:
        return None
    return expected_mfe_bps / expected_mae_bps


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _cap_from_score(score: float, *, risk_max: int) -> int:
    return max(0, min(risk_max, 6 + int(round((risk_max - 6) * _clamp01(score)))))


def _edge_score(
    *,
    expected_return_bps: float | None,
    projected_rr: float | None,
    decision_confidence: float,
    trade_score: float,
    min_expected_return_bps: float,
    min_projected_rr: float,
) -> float:
    edge_component = 0.0
    if expected_return_bps is not None and min_expected_return_bps > 0:
        edge_component = _clamp01(expected_return_bps / max(min_expected_return_bps * 6.0, 1.0))
    rr_component = 0.0
    if projected_rr is not None and min_projected_rr > 0:
        rr_component = _clamp01(projected_rr / max(min_projected_rr * 3.0, 1.0))
    return _clamp01(
        0.40 * edge_component
        + 0.25 * rr_component
        + 0.20 * _clamp01(decision_confidence)
        + 0.15 * _clamp01(trade_score)
    )


def _cost_score(*, value: float | None, hard_limit: float, scale: float) -> float:
    if value is None or hard_limit <= 0:
        return 0.0
    return _clamp01(1.0 - (value / max(hard_limit * scale, 0.0001)))


def _depth_score(
    *,
    depth_ratio: float | None,
    impact_bps: float | None,
    min_depth_ratio: float,
    max_impact_bps: float,
    liquidity_source: str,
) -> float:
    if depth_ratio is None or impact_bps is None:
        return 0.0
    depth_component = _clamp01(depth_ratio / max(min_depth_ratio * 2.0, 0.0001))
    impact_component = _cost_score(value=impact_bps, hard_limit=max_impact_bps, scale=1.0)
    score = min(depth_component, impact_component)
    if liquidity_source != "orderbook_levels":
        score = min(score, 0.05)
    return score


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _unique_strs(values: list[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if value not in out:
            out.append(value)
    return out
