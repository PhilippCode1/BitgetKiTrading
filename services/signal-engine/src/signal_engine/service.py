"""
Orchestrierung: Kontext laden, 6 Schichten, Composite, Rejection, Richtung, Persistenz.
"""

from __future__ import annotations

import logging
import math
from typing import Any
from uuid import uuid4

from signal_engine.config import SignalEngineSettings, normalize_timeframe
from signal_engine.models import ScoringContext
from signal_engine.scoring.classification import classify_signal
from signal_engine.scoring.composite_score import weighted_composite
from signal_engine.scoring.history_score import score_history
from signal_engine.scoring.momentum_score import score_momentum
from signal_engine.scoring.multi_timeframe_score import score_multi_timeframe
from signal_engine.scoring.news_score import score_news
from signal_engine.scoring.regime_classifier import classify_market_regime
from signal_engine.scoring.rejection_rules import apply_rejections
from signal_engine.scoring.risk_score import _first_geometry, _reward_risk_ratio, score_risk
from signal_engine.explain.builder import build_explanation_bundle
from signal_engine.explain.schemas import ExplainInput
from signal_engine.decision_control_flow import attach_decision_control_flow_to_bundle
from signal_engine.meta_decision_kernel import apply_meta_decision_kernel
from signal_engine.hybrid_decision import assess_hybrid_decision
from signal_engine.specialists import build_specialist_stack
from signal_engine.scoring.structure_score import score_structure
from signal_engine.take_trade_model import TakeTradeModelScorer
from signal_engine.target_bps_models import TargetBpsModelScorer
from signal_engine.uncertainty import assess_model_uncertainty
from signal_engine.stop_budget_policy import STOP_BUDGET_POLICY_VERSION, assess_stop_budget_policy
from shared_py.structured_market_context import (
    assess_structured_market_context,
    merge_live_reasons_into_risk_governor,
    refine_structured_market_context_for_playbook,
)
from shared_py.unified_leverage_allocator import refresh_unified_leverage_allocation_in_snapshot
from signal_engine.storage.explanations_repo import ExplanationRepository
from signal_engine.storage.repo import SignalRepository, all_timeframes
from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetInstrumentMetadataService,
    BitgetSettings,
)
from shared_py.bitget.instruments import BitgetInstrumentIdentity
from shared_py.model_contracts import (
    MODEL_OUTPUT_SCHEMA_HASH,
    MODEL_OUTPUT_SCHEMA_VERSION,
    build_feature_snapshot,
    build_model_contract_bundle,
    build_quality_gate,
    extract_active_models_from_signal_row,
    normalize_feature_row,
    normalize_model_timeframe,
)
from shared_py.replay_determinism import (
    stable_decision_trace_id,
    stable_signal_row_id,
    trace_implies_replay_determinism,
)
from shared_py.signal_contracts import SIGNAL_EVENT_SCHEMA_VERSION
from shared_py.unified_exit_plan import build_unified_exit_plan
from shared_py.uncertainty_gates import merge_meta_trade_lanes


def _replay_session_id_from_trace(trace: dict[str, Any] | None) -> str | None:
    if not trace:
        return None
    sid = trace.get("session_id")
    if sid:
        return str(sid)
    det = trace.get("determinism")
    if isinstance(det, dict) and det.get("replay_session_id"):
        return str(det["replay_session_id"])
    return None


def _resolve_signal_row_id(
    *,
    settings: SignalEngineSettings,
    causal_trace: dict[str, Any] | None,
    upstream_event_id: str | None,
    ctx: ScoringContext,
    signal_output_schema_version: str,
) -> str:
    if not settings.signal_stable_replay_signal_ids:
        return str(uuid4())
    if not causal_trace or not upstream_event_id:
        return str(uuid4())
    if not trace_implies_replay_determinism(causal_trace):
        return str(uuid4())
    rs = _replay_session_id_from_trace(causal_trace)
    if not rs:
        return str(uuid4())
    return stable_signal_row_id(
        replay_session_id=rs,
        upstream_event_id=str(upstream_event_id),
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        analysis_ts_ms=ctx.analysis_ts_ms,
        signal_output_schema_version=signal_output_schema_version,
    )


def structure_trend_sign(structure_state: dict[str, Any] | None) -> int:
    if structure_state is None:
        return 0
    t = str(structure_state.get("trend_dir", "RANGE"))
    if t == "UP":
        return 1
    if t == "DOWN":
        return -1
    return 0


def propose_direction(
    ctx: ScoringContext,
    settings: SignalEngineSettings,
    *,
    structure_s: float,
    mtf_s: float,
    momentum_flags: list[str],
) -> str:
    st = ctx.structure_state
    if st is None:
        return "neutral"
    trend = str(st.get("trend_dir", "RANGE"))
    if trend not in ("UP", "DOWN"):
        return "neutral"
    if structure_s < settings.signal_min_structure_score_for_directional:
        return "neutral"
    if mtf_s < settings.signal_min_multi_tf_score_for_directional:
        return "neutral"
    if trend == "UP" and "momentum_vs_structure_up" in momentum_flags:
        return "neutral"
    if trend == "DOWN" and "momentum_vs_structure_down" in momentum_flags:
        return "neutral"
    return "long" if trend == "UP" else "short"


def compute_probability(
    *,
    composite: float,
    multi_tf: float,
    risk: float,
    direction: str,
    decision_state: str,
) -> float:
    c = composite / 100.0
    m = multi_tf / 100.0
    r = risk / 100.0
    p = 0.1 + 0.55 * c * (0.55 + 0.45 * m) * (0.5 + 0.5 * r)
    if direction == "neutral":
        p *= 0.58
    if decision_state == "rejected":
        return max(0.05, min(0.95, p * 0.22))
    if decision_state == "downgraded":
        p *= 0.8
    return max(0.06, min(0.91, p))


def build_reasons_object(
    *,
    direction: str,
    layer_notes: dict[str, list[str]],
    decisive: list[str],
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bullish: list[str] = []
    bearish: list[str] = []
    if direction == "long":
        bullish.append("structure_bias_long")
    elif direction == "short":
        bearish.append("structure_bias_short")
    else:
        bullish.append("neutral_bias")
        bearish.append("neutral_bias")
    return {
        "bullish_factors": bullish,
        "bearish_factors": bearish,
        "market_regime": regime.get("market_regime") if regime else None,
        "regime_state": regime.get("regime_state") if regime else None,
        "regime_bias": regime.get("regime_bias") if regime else None,
        "regime_notes": list(regime.get("regime_reasons_json") or []) if regime else [],
        "structural_notes": layer_notes.get("structure", []),
        "momentum_notes": layer_notes.get("momentum", []),
        "timeframe_notes": layer_notes.get("multi_tf", []),
        "risk_notes": layer_notes.get("risk", []),
        "news_notes": layer_notes.get("news", []),
        "history_notes": layer_notes.get("history", []),
        "decisive_factors": decisive,
    }


def _news_ts_ms(news_row: dict[str, Any] | None) -> int | None:
    if not news_row:
        return None
    for key in ("scored_ts_ms", "published_ts_ms", "ingested_ts_ms"):
        raw = news_row.get(key)
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    published = news_row.get("published_ts")
    if hasattr(published, "timestamp"):
        return int(published.timestamp() * 1000)
    return None


def _feature_quality_labels(
    *,
    timeframe: str,
    row: dict[str, Any] | None,
    analysis_ts_ms: int,
    max_age_ms: int,
    primary: bool,
) -> list[str]:
    issues: list[str] = []
    if row is None:
        issues.append("missing_primary_features" if primary else f"missing_feature_tf_{timeframe}")
        return issues
    _, contract_issues = normalize_feature_row(row)
    if contract_issues:
        issues.append("invalid_primary_feature_contract" if primary else f"invalid_feature_tf_{timeframe}")
        if any(item.endswith("schema_hash_mismatch") for item in contract_issues):
            issues.append(
                "primary_feature_schema_mismatch"
                if primary
                else f"feature_schema_mismatch_{timeframe}"
            )
    computed_ts_ms = int(row.get("computed_ts_ms") or 0)
    if computed_ts_ms <= 0:
        issues.append("invalid_primary_feature_contract" if primary else f"invalid_feature_tf_{timeframe}")
    elif computed_ts_ms > analysis_ts_ms:
        issues.append("feature_data_from_future" if primary else f"feature_from_future_{timeframe}")
    elif analysis_ts_ms - computed_ts_ms > max_age_ms:
        issues.append("stale_feature_data" if primary else f"stale_feature_tf_{timeframe}")
    return issues


def _feature_float(row: dict[str, Any] | None, field: str) -> float | None:
    if row is None:
        return None
    value = row.get(field)
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _feature_source(row: dict[str, Any] | None, field: str) -> str | None:
    if row is None:
        return None
    raw = str(row.get(field) or "").strip()
    return raw or None


def _collect_primary_market_feature_issues(
    *,
    settings: SignalEngineSettings,
    row: dict[str, Any] | None,
) -> list[str]:
    if row is None:
        return []
    issues: list[str] = []

    liquidity_source = _feature_source(row, "liquidity_source")
    orderbook_age_ms = _feature_float(row, "orderbook_age_ms")
    if liquidity_source in (None, "missing"):
        issues.append("missing_liquidity_context")
    elif liquidity_source != "orderbook_levels":
        issues.append("liquidity_context_fallback")
    if orderbook_age_ms is not None and orderbook_age_ms > settings.signal_max_orderbook_age_ms:
        issues.append("stale_orderbook_feature_data")
    if _feature_float(row, "spread_bps") is None:
        issues.append("missing_spread_feature")
    if _feature_float(row, "execution_cost_bps") is None:
        issues.append("missing_execution_cost_feature")
    if liquidity_source == "orderbook_levels":
        if _feature_float(row, "impact_buy_bps_5000") is None:
            issues.append("missing_slippage_proxy")
        if _feature_float(row, "impact_sell_bps_5000") is None:
            issues.append("missing_slippage_proxy")

    funding_source = _feature_source(row, "funding_source")
    funding_age_ms = _feature_float(row, "funding_age_ms")
    if funding_source in (None, "missing"):
        issues.append("missing_funding_context")
    if funding_age_ms is not None and funding_age_ms > settings.signal_max_funding_feature_age_ms:
        issues.append("stale_funding_feature_data")
    if _feature_float(row, "funding_rate_bps") is None:
        issues.append("missing_funding_feature")

    open_interest_source = _feature_source(row, "open_interest_source")
    open_interest_age_ms = _feature_float(row, "open_interest_age_ms")
    if open_interest_source in (None, "missing"):
        issues.append("missing_open_interest_context")
    if open_interest_age_ms is not None and open_interest_age_ms > settings.signal_max_open_interest_age_ms:
        issues.append("stale_open_interest_feature_data")
    if _feature_float(row, "open_interest") is None:
        issues.append("missing_open_interest_feature")
    if _feature_float(row, "open_interest_change_pct") is None:
        issues.append("missing_open_interest_delta")

    return sorted(set(issues))


def _collect_data_quality_issues(
    *,
    settings: SignalEngineSettings,
    analysis_ts_ms: int,
    timeframe: str,
    primary_feature: dict[str, Any] | None,
    features_by_tf: dict[str, dict[str, Any] | None],
    structure_state: dict[str, Any] | None,
    drawings: list[dict[str, Any]],
    news_row: dict[str, Any] | None,
    last_close: float | None,
) -> list[str]:
    issues: list[str] = []
    issues.extend(
        _feature_quality_labels(
            timeframe=timeframe,
            row=primary_feature,
            analysis_ts_ms=analysis_ts_ms,
            max_age_ms=settings.signal_max_data_age_ms,
            primary=True,
        )
    )
    for tf, row in features_by_tf.items():
        if tf == timeframe:
            continue
        issues.extend(
            _feature_quality_labels(
                timeframe=tf,
                row=row,
                analysis_ts_ms=analysis_ts_ms,
                max_age_ms=settings.signal_max_data_age_ms,
                primary=False,
            )
        )
    issues.extend(
        _collect_primary_market_feature_issues(
            settings=settings,
            row=primary_feature,
        )
    )

    if structure_state is None:
        issues.append("missing_structure_state")
    else:
        trend_dir = str(structure_state.get("trend_dir") or "")
        if trend_dir not in ("UP", "DOWN", "RANGE"):
            issues.append("invalid_structure_state")
        ref_ts_ms = int(structure_state.get("updated_ts_ms") or structure_state.get("last_ts_ms") or 0)
        if ref_ts_ms <= 0:
            issues.append("invalid_structure_state_timestamp")
        elif ref_ts_ms > analysis_ts_ms:
            issues.append("structure_state_from_future")
        elif analysis_ts_ms - ref_ts_ms > settings.signal_max_structure_age_ms:
            issues.append("stale_structure_state")

    if last_close is None:
        issues.append("missing_last_close")
    elif not math.isfinite(last_close) or last_close <= 0:
        issues.append("invalid_last_close")

    if not drawings:
        issues.append("missing_drawings")
    else:
        latest_draw_ts = max(int(d.get("updated_ts_ms") or d.get("created_ts_ms") or 0) for d in drawings)
        if latest_draw_ts <= 0:
            issues.append("invalid_drawing_timestamp")
        elif latest_draw_ts > analysis_ts_ms:
            issues.append("drawing_state_from_future")
        elif analysis_ts_ms - latest_draw_ts > settings.signal_max_drawing_age_ms:
            issues.append("stale_drawing_data")
        if not any(d.get("type") == "stop_zone" and isinstance(d.get("geometry"), dict) for d in drawings):
            issues.append("missing_stop_zone")
        if not any(d.get("type") == "target_zone" and isinstance(d.get("geometry"), dict) for d in drawings):
            issues.append("missing_target_zone")
        if any(
            not 0 <= float(d.get("confidence")) <= 100
            for d in drawings
            if d.get("confidence") is not None
        ):
            issues.append("invalid_drawing_confidence")

    if news_row is not None:
        news_ts_ms = _news_ts_ms(news_row)
        if news_ts_ms is None:
            issues.append("invalid_news_timestamp")
        elif news_ts_ms > analysis_ts_ms:
            issues.append("news_context_from_future")
        elif analysis_ts_ms - news_ts_ms > settings.signal_max_news_age_ms:
            issues.append("stale_news_context")
        relevance = news_row.get("relevance_score")
        if relevance is not None:
            try:
                rel = float(relevance)
            except (TypeError, ValueError):
                issues.append("invalid_news_relevance")
            else:
                if not 0 <= rel <= 100:
                    issues.append("invalid_news_relevance")

    return sorted(set(issues))


def run_scoring_pipeline(
    ctx: ScoringContext,
    settings: SignalEngineSettings,
    *,
    prior_total: int,
    prior_avg: float | None,
    causal_trace: dict[str, Any] | None = None,
    upstream_event_id: str | None = None,
) -> dict[str, Any]:
    """Deterministische Pipeline -> DB-Row + event_payload (ohne DB)."""
    sig = structure_trend_sign(ctx.structure_state)
    regime = classify_market_regime(
        ctx,
        news_shock_feature_enabled=settings.signal_news_shock_rejection_enabled,
    )
    ls = score_structure(ctx)
    lm = score_momentum(ctx)
    lmt = score_multi_timeframe(ctx, primary_structure_sign=sig)
    ln = score_news(ctx, settings)
    lr = score_risk(
        ctx,
        market_regime=regime.market_regime,
        regime_bias=regime.regime_bias,
    )
    lh = score_history(
        ctx, settings, prior_avg_strength=prior_avg, prior_count=prior_total
    )

    weights = settings.weight_tuple()
    composite = weighted_composite(
        ls.score,
        lm.score,
        lmt.score,
        ln.score,
        lr.score,
        lh.score,
        weights,
    )

    layer_flags = list(
        dict.fromkeys(ls.flags + lm.flags + lmt.flags + ln.flags + lr.flags + lh.flags)
    )
    direction = propose_direction(
        ctx,
        settings,
        structure_s=ls.score,
        mtf_s=lmt.score,
        momentum_flags=lm.flags,
    )

    instrument_for_smc = ctx.instrument or settings.instrument_identity(symbol=ctx.symbol)
    smc = assess_structured_market_context(
        news_row=ctx.news_row,
        symbol=ctx.symbol,
        market_family=str(instrument_for_smc.market_family),
        proposed_direction=direction,
        analysis_ts_ms=ctx.analysis_ts_ms,
        structure_events=ctx.structure_events,
        primary_feature=ctx.primary_feature,
        settings=settings,
    )

    rej = apply_rejections(
        ctx,
        settings,
        composite=composite,
        structure_score=ls.score,
        multi_tf_score=lmt.score,
        risk_score=lr.score,
        proposed_direction=direction,
        layer_flags=layer_flags,
        structured_rejection_soft=list(smc.get("deterministic_rejection_soft_json") or []),
        structured_rejection_hard=list(smc.get("deterministic_rejection_hard_json") or []),
    )

    strength = composite
    if rej.decision_state == "rejected":
        strength = min(strength, 22.0)
    elif rej.decision_state == "downgraded":
        strength = min(strength, composite * 0.84)
    try:
        shrink_ctx = float(smc.get("composite_effective_factor_0_1") or 1.0)
    except (TypeError, ValueError):
        shrink_ctx = 1.0
    shrink_ctx = max(0.0, min(1.0, shrink_ctx))
    strength = strength * shrink_ctx

    signal_class = classify_signal(
        settings,
        composite_strength=strength,
        decision_state=rej.decision_state,
        layer_flags=layer_flags,
        multi_tf_score=lmt.score,
        risk_score=lr.score,
        market_regime=regime.market_regime,
    )

    probability = compute_probability(
        composite=strength,
        multi_tf=lmt.score,
        risk=lr.score,
        direction=direction,
        decision_state=rej.decision_state,
    )

    layer_notes = {
        "structure": ls.notes,
        "momentum": lm.notes,
        "multi_tf": lmt.notes,
        "news": ln.notes,
        "risk": lr.notes,
        "history": lh.notes,
    }
    decisive = [
        f"composite={composite:.2f}",
        f"decision={rej.decision_state}",
        f"class={signal_class}",
        f"direction_rule=structure_plus_mtf_gates",
    ]
    reasons_json = build_reasons_object(
        direction=direction,
        layer_notes=layer_notes,
        decisive=decisive,
        regime={
            "market_regime": regime.market_regime,
            "regime_state": regime.regime_state,
            "regime_bias": regime.regime_bias,
            "regime_reasons_json": regime.regime_reasons_json,
        },
    )
    reasons_json["deterministic_gates"] = {
        "rejection_state": rej.rejection_state,
        "decision_state": rej.decision_state,
        "rejection_reasons_json": list(rej.rejection_reasons),
    }
    reasons_json["structured_market_context_summary"] = {
        "version": smc.get("version"),
        "instrument_context_key": smc.get("instrument_context_key"),
        "facets_active_json": smc.get("facets_active_json"),
        "surprise_score_0_1": smc.get("surprise_score_0_1"),
        "decay_factor_0_1": smc.get("decay_factor_0_1"),
        "conflict_codes_json": smc.get("conflict_codes_json"),
        "composite_effective_factor_0_1": smc.get("composite_effective_factor_0_1"),
    }

    drawings = ctx.drawings
    stop_d = next((d for d in drawings if d.get("type") == "stop_zone"), None)
    targets = [d for d in drawings if d.get("type") == "target_zone"]
    stop_geo = _first_geometry(drawings, "stop_zone")
    rr = _reward_risk_ratio(ctx.last_close, stop_geo, targets)

    signal_id = _resolve_signal_row_id(
        settings=settings,
        causal_trace=causal_trace,
        upstream_event_id=upstream_event_id,
        ctx=ctx,
        signal_output_schema_version=SIGNAL_EVENT_SCHEMA_VERSION,
    )
    market_regime = regime.market_regime
    ev_band = None
    if ctx.primary_feature and ctx.primary_feature.get("atrp_14") is not None:
        ev_band = float(ctx.primary_feature["atrp_14"])

    components_hist = [
        {"layer": "structure", "score": ls.score, "notes": ls.notes},
        {"layer": "momentum", "score": lm.score, "notes": lm.notes},
        {"layer": "multi_timeframe", "score": lmt.score, "notes": lmt.notes},
        {"layer": "news", "score": ln.score, "notes": ln.notes},
        {"layer": "risk", "score": lr.score, "notes": lr.notes},
        {"layer": "history", "score": lh.score, "notes": lh.notes},
        {
            "layer": "regime",
            "market_regime": regime.market_regime,
            "regime_state": regime.regime_state,
            "regime_substate": regime.regime_substate,
            "transition_state": regime.regime_transition_state,
            "persistence_bars": regime.regime_persistence_bars,
            "regime_bias": regime.regime_bias,
            "confidence_0_1": regime.regime_confidence_0_1,
            "notes": regime.regime_reasons_json,
        },
        {"layer": "weights", "values": list(weights)},
        {
            "layer": "structured_market_context",
            "version": smc.get("version"),
            "instrument_context_key": smc.get("instrument_context_key"),
            "facets_active_json": smc.get("facets_active_json"),
            "surprise_score_0_1": smc.get("surprise_score_0_1"),
            "composite_effective_factor_0_1": smc.get("composite_effective_factor_0_1"),
        },
    ]

    quality_gate = build_quality_gate(ctx.data_issues)
    feature_snapshot = build_feature_snapshot(
        primary_timeframe=ctx.timeframe,
        primary_feature=ctx.primary_feature,
        features_by_tf=ctx.features_by_tf,
        quality_issues=ctx.data_issues,
    )
    instrument = ctx.instrument or settings.instrument_identity(symbol=ctx.symbol)
    source_snapshot = {
        "has_structure": ctx.structure_state is not None,
        "has_primary_feature": ctx.primary_feature is not None,
        "drawings_count": len(drawings),
        "structure_events_count": len(ctx.structure_events),
        "last_close": ctx.last_close,
        "data_issues": ctx.data_issues,
        "quality_gate": quality_gate,
        "regime_snapshot": regime.regime_snapshot,
        "instrument": instrument.model_dump(mode="json"),
        "canonical_instrument_id": ctx.canonical_instrument_id,
        "feature_snapshot": feature_snapshot,
        "take_trade_model": None,
        "target_projection_summary": None,
        "target_projection_models": [],
        "uncertainty_assessment": None,
        "hybrid_decision": None,
        "model_contract": build_model_contract_bundle(quality_issues=ctx.data_issues),
        "correlation_chain": {
            "schema": "correlation-v1",
            "signal_id": signal_id,
            "upstream_drawing_updated_event_id": upstream_event_id,
            "replay_session_id": _replay_session_id_from_trace(causal_trace),
            "candle_close_event_id": (causal_trace or {}).get("candle_close_event_id"),
            "structure_updated_event_id": (causal_trace or {}).get("structure_updated_event_id"),
        },
        "instrument_execution": ctx.instrument_execution_meta or {},
        "structured_market_context": smc,
    }

    row = {
        "signal_id": signal_id,
        "canonical_instrument_id": ctx.canonical_instrument_id,
        "symbol": ctx.symbol,
        "timeframe": ctx.timeframe,
        "analysis_ts_ms": ctx.analysis_ts_ms,
        "market_family": instrument.market_family,
        "market_regime": market_regime,
        "regime_state": regime.regime_state,
        "regime_bias": regime.regime_bias,
        "regime_confidence_0_1": regime.regime_confidence_0_1,
        "regime_reasons_json": regime.regime_reasons_json,
        "regime_substate": regime.regime_substate,
        "regime_transition_state": regime.regime_transition_state,
        "regime_transition_reasons_json": regime.regime_transition_reasons_json,
        "regime_persistence_bars": regime.regime_persistence_bars,
        "regime_policy_version": regime.regime_snapshot.get("regime_policy_version"),
        "direction": direction,
        "signal_strength_0_100": strength,
        "probability_0_1": probability,
        "take_trade_prob": None,
        "take_trade_model_version": None,
        "take_trade_model_run_id": None,
        "take_trade_calibration_method": None,
        "expected_return_bps": None,
        "expected_mae_bps": None,
        "expected_mfe_bps": None,
        "target_projection_models_json": [],
        "model_uncertainty_0_1": None,
        "shadow_divergence_0_1": None,
        "model_ood_score_0_1": None,
        "model_ood_alert": False,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": list(rej.rejection_reasons) if rej.rejection_state else [],
        "trade_action": "do_not_trade" if rej.rejection_state else "allow_trade",
        "meta_trade_lane": None,
        "decision_confidence_0_1": None,
        "decision_policy_version": None,
        "allowed_leverage": None,
        "recommended_leverage": None,
        "execution_leverage_cap": None,
        "mirror_leverage": None,
        "unified_leverage_allocator_version": None,
        "leverage_policy_version": None,
        "leverage_cap_reasons_json": [],
        "signal_class": signal_class,
        "structure_score_0_100": ls.score,
        "momentum_score_0_100": lm.score,
        "multi_timeframe_score_0_100": lmt.score,
        "news_score_0_100": ln.score,
        "risk_score_0_100": lr.score,
        "history_score_0_100": lh.score,
        "weighted_composite_score_0_100": composite,
        "rejection_state": rej.rejection_state,
        "rejection_reasons_json": rej.rejection_reasons,
        "decision_state": rej.decision_state,
        "reasons_json": reasons_json,
        "supporting_drawing_ids_json": [d["drawing_id"] for d in drawings],
        "supporting_structure_event_ids_json": [
            str(e.get("event_id", "")) for e in ctx.structure_events[:20]
        ],
        "stop_zone_id": stop_d["drawing_id"] if stop_d else None,
        "target_zone_ids_json": [t["drawing_id"] for t in targets],
        "reward_risk_ratio": rr,
        "expected_volatility_band": ev_band,
        "strategy_name": None,
        "playbook_id": None,
        "playbook_family": None,
        "playbook_decision_mode": "playbookless",
        "playbook_registry_version": None,
        "source_snapshot_json": source_snapshot,
        "scoring_model_version": settings.signal_scoring_model_version,
        "signal_components_history_json": components_hist,
        "stop_distance_pct": None,
        "stop_budget_max_pct_allowed": None,
        "stop_min_executable_pct": None,
        "stop_to_spread_ratio": None,
        "stop_quality_0_1": None,
        "stop_executability_0_1": None,
        "stop_fragility_0_1": None,
        "stop_budget_policy_version": None,
        "meta_decision_action": "do_not_trade",
        "meta_decision_kernel_version": None,
        "meta_decision_bundle_json": {},
        "operator_override_audit_json": None,
    }

    event_payload = {
        "schema_version": SIGNAL_EVENT_SCHEMA_VERSION,
        "signal_id": signal_id,
        "symbol": ctx.symbol,
        "market_family": instrument.market_family,
        "margin_account_mode": instrument.margin_account_mode,
        "timeframe": ctx.timeframe,
        "direction": direction,
        "signal_strength_0_100": strength,
        "probability_0_1": probability,
        "take_trade_prob": None,
        "take_trade_model_version": None,
        "take_trade_model_run_id": None,
        "take_trade_calibration_method": None,
        "expected_return_bps": None,
        "expected_mae_bps": None,
        "expected_mfe_bps": None,
        "model_uncertainty_0_1": None,
        "shadow_divergence_0_1": None,
        "model_ood_score_0_1": None,
        "model_ood_alert": False,
        "uncertainty_reasons_json": [],
        "ood_reasons_json": [],
        "abstention_reasons_json": list(rej.rejection_reasons) if rej.rejection_state else [],
        "trade_action": "do_not_trade" if rej.rejection_state else "allow_trade",
        "meta_trade_lane": None,
        "decision_confidence_0_1": None,
        "decision_policy_version": None,
        "allowed_leverage": None,
        "recommended_leverage": None,
        "execution_leverage_cap": None,
        "mirror_leverage": None,
        "unified_leverage_allocator_version": None,
        "leverage_policy_version": None,
        "leverage_cap_reasons_json": [],
        "signal_class": signal_class,
        "decision_state": rej.decision_state,
        "rejection_state": rej.rejection_state,
        "rejection_reasons_json": rej.rejection_reasons,
        "analysis_ts_ms": ctx.analysis_ts_ms,
        "market_regime": market_regime,
        "regime_state": regime.regime_state,
        "regime_bias": regime.regime_bias,
        "regime_confidence_0_1": regime.regime_confidence_0_1,
        "regime_reasons_json": regime.regime_reasons_json,
        "regime_substate": regime.regime_substate,
        "regime_transition_state": regime.regime_transition_state,
        "regime_transition_reasons_json": regime.regime_transition_reasons_json,
        "regime_persistence_bars": regime.regime_persistence_bars,
        "regime_policy_version": regime.regime_snapshot.get("regime_policy_version"),
        "playbook_id": None,
        "playbook_family": None,
        "playbook_decision_mode": "playbookless",
        "playbook_registry_version": None,
        "strategy_name": None,
        "scoring_model_version": settings.signal_scoring_model_version,
        "model_output_schema_version": MODEL_OUTPUT_SCHEMA_VERSION,
        "model_output_schema_hash": MODEL_OUTPUT_SCHEMA_HASH,
        "feature_schema_version": feature_snapshot["feature_schema_version"],
        "feature_schema_hash": feature_snapshot["feature_schema_hash"],
        "quality_gate": quality_gate,
        "correlation_chain": source_snapshot["correlation_chain"],
        "instrument": instrument.model_dump(mode="json"),
    }
    return {"db_row": row, "event_payload": event_payload}


class SignalEngineService:
    def __init__(
        self,
        settings: SignalEngineSettings,
        repo: SignalRepository,
        explain_repo: ExplanationRepository,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._explain_repo = explain_repo
        self._logger = logger or logging.getLogger("signal_engine.service")
        self._catalog = BitgetInstrumentCatalog(
            bitget_settings=BitgetSettings(),
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            source_service="signal-engine",
            cache_ttl_sec=settings.instrument_catalog_cache_ttl_sec,
            max_stale_sec=settings.instrument_catalog_max_stale_sec,
        )
        self._metadata_service = BitgetInstrumentMetadataService(self._catalog)
        self._take_trade_model = TakeTradeModelScorer(
            repo,
            refresh_ms=settings.take_trade_model_refresh_ms,
            ood_robust_z_threshold=settings.model_ood_robust_z_threshold,
            ood_max_flagged_features=settings.model_ood_max_flagged_features,
            logger=self._logger,
            registry_scoped_slots_enabled=settings.model_registry_scoped_slots_enabled,
        )
        self._target_bps_models = TargetBpsModelScorer(
            repo,
            refresh_ms=settings.take_trade_model_refresh_ms,
            ood_robust_z_threshold=settings.model_ood_robust_z_threshold,
            ood_max_flagged_features=settings.model_ood_max_flagged_features,
            logger=self._logger,
        )

    def load_context(self, symbol: str, timeframe: str, analysis_ts_ms: int) -> ScoringContext:
        tf = normalize_timeframe(timeframe)
        (
            instrument,
            canonical_instrument_id,
            instrument_issues,
            instrument_execution_meta,
        ) = self._resolve_context_instrument(symbol)
        previous_regime = self._repo.fetch_previous_regime_snapshot(
            symbol=symbol,
            timeframe=tf,
            max_analysis_ts_ms=analysis_ts_ms,
            canonical_instrument_id=canonical_instrument_id,
            market_family=instrument.market_family if instrument else None,
        )
        st = self._repo.fetch_structure_state(
            symbol=symbol,
            timeframe=tf,
            max_ts_ms=analysis_ts_ms,
        )
        evs = self._repo.fetch_structure_events(
            symbol=symbol,
            timeframe=tf,
            max_ts_ms=analysis_ts_ms,
        )
        raw_primary_feature = self._repo.fetch_latest_feature(
            symbol=symbol,
            timeframe=tf,
            max_start_ts_ms=analysis_ts_ms,
            canonical_instrument_id=canonical_instrument_id,
            market_family=instrument.market_family if instrument else None,
        )
        pf, _ = normalize_feature_row(raw_primary_feature)
        raw_feature_map = self._repo.fetch_features_by_timeframes(
            symbol=symbol,
            timeframes=all_timeframes(),
            max_start_ts_ms=analysis_ts_ms,
            canonical_instrument_id=canonical_instrument_id,
            market_family=instrument.market_family if instrument else None,
        )
        fmap: dict[str, dict[str, Any] | None] = {}
        for feature_tf, raw_row in raw_feature_map.items():
            normalized, _ = normalize_feature_row(raw_row)
            fmap[normalize_model_timeframe(feature_tf)] = normalized
        if pf is not None:
            fmap[tf] = pf
        dr = self._repo.fetch_active_drawings(
            symbol=symbol,
            timeframe=tf,
            max_ts_ms=analysis_ts_ms,
        )
        news = self._repo.fetch_latest_news(symbol=symbol, max_ts_ms=analysis_ts_ms)
        close = self._repo.fetch_latest_close(
            symbol=symbol,
            timeframe=tf,
            max_start_ts_ms=analysis_ts_ms,
        )
        issues = _collect_data_quality_issues(
            settings=self._settings,
            analysis_ts_ms=analysis_ts_ms,
            timeframe=tf,
            primary_feature=pf,
            features_by_tf=fmap,
            structure_state=st,
            drawings=dr,
            news_row=news,
            last_close=close,
        )
        issues = list(dict.fromkeys(list(issues) + instrument_issues))
        return ScoringContext(
            symbol=symbol,
            timeframe=tf,
            analysis_ts_ms=analysis_ts_ms,
            structure_state=st,
            structure_events=evs,
            primary_feature=pf,
            features_by_tf=fmap,
            drawings=dr,
            news_row=news,
            last_close=close,
            instrument=instrument,
            canonical_instrument_id=canonical_instrument_id,
            previous_regime_snapshot=(
                previous_regime.get("source_regime_snapshot") or previous_regime
                if isinstance(previous_regime, dict)
                else None
            ),
            data_issues=issues,
            instrument_execution_meta=instrument_execution_meta,
        )

    def evaluate_and_persist(
        self,
        symbol: str,
        timeframe: str,
        analysis_ts_ms: int,
        *,
        causal_trace: dict[str, Any] | None = None,
        upstream_event_id: str | None = None,
    ) -> dict[str, Any]:
        ctx = self.load_context(symbol, timeframe, analysis_ts_ms)
        prior_total, prior_avg = self._repo.fetch_prior_signal_stats(
            symbol=ctx.symbol, timeframe=ctx.timeframe
        )
        bundle = run_scoring_pipeline(
            ctx,
            self._settings,
            prior_total=prior_total,
            prior_avg=prior_avg,
            causal_trace=causal_trace,
            upstream_event_id=upstream_event_id,
        )
        self._apply_catalog_resolution(bundle, ctx.symbol)
        take_trade_prediction = self._apply_take_trade_model(bundle, ctx)
        target_projection = self._apply_target_bps_models(bundle, ctx)
        self._apply_uncertainty_policy(
            bundle,
            ctx,
            take_trade_prediction=take_trade_prediction,
            target_projection=target_projection,
        )
        self._apply_hybrid_decision(bundle)
        self._apply_stop_budget_policy(bundle, ctx)
        self._apply_online_drift_guard(bundle)
        self._apply_specialist_stack(bundle)
        self._apply_meta_decision_kernel(bundle)
        self._finalize_decision_control_flow(bundle)
        self._apply_unified_exit_plan(bundle)
        self._repo.insert_signal_v1(bundle["db_row"])
        sig_row = dict(bundle["db_row"])
        sig_row["stop_trigger_type"] = self._settings.signal_default_stop_trigger_type
        explain_inp = ExplainInput(
            signal_row=sig_row,
            structure_state=ctx.structure_state,
            structure_events=list(ctx.structure_events),
            primary_feature=ctx.primary_feature,
            features_by_tf=dict(ctx.features_by_tf),
            drawings=list(ctx.drawings),
            news_row=ctx.news_row,
            last_close=ctx.last_close,
        )
        exp_bundle = build_explanation_bundle(explain_inp, self._settings)
        self._explain_repo.upsert_for_signal(
            signal_id=str(bundle["db_row"]["signal_id"]),
            bundle=exp_bundle,
        )
        self._logger.info(
            "signal persisted id=%s dir=%s class=%s decision=%s",
            bundle["db_row"]["signal_id"],
            bundle["db_row"]["direction"],
            bundle["db_row"]["signal_class"],
            bundle["db_row"]["decision_state"],
        )
        return bundle

    def _apply_take_trade_model(self, bundle: dict[str, Any], ctx: ScoringContext) -> dict[str, Any]:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        feature_snapshot = source_snapshot.get("feature_snapshot")
        prediction = self._take_trade_model.predict(
            signal_row=db_row,
            feature_snapshot=feature_snapshot if isinstance(feature_snapshot, dict) else None,
        )
        db_row["take_trade_prob"] = prediction.get("take_trade_prob")
        db_row["take_trade_model_version"] = prediction.get("take_trade_model_version")
        db_row["take_trade_model_run_id"] = prediction.get("take_trade_model_run_id")
        db_row["take_trade_calibration_method"] = prediction.get("take_trade_calibration_method")
        if isinstance(source_snapshot, dict):
            source_snapshot["take_trade_model"] = prediction.get("take_trade_model_info")
            source_snapshot["model_contract"] = build_model_contract_bundle(
                quality_issues=ctx.data_issues,
                active_models=extract_active_models_from_signal_row(db_row),
            )
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list) and prediction.get("take_trade_prob") is not None:
            comp_hist.append(
                {
                    "layer": "take_trade_meta_model",
                    "probability": prediction.get("take_trade_prob"),
                    "model_version": prediction.get("take_trade_model_version"),
                    "run_id": prediction.get("take_trade_model_run_id"),
                    "calibration_method": prediction.get("take_trade_calibration_method"),
                }
            )
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["take_trade_prob"] = prediction.get("take_trade_prob")
            event_payload["take_trade_model_version"] = prediction.get("take_trade_model_version")
            event_payload["take_trade_model_run_id"] = prediction.get("take_trade_model_run_id")
            event_payload["take_trade_calibration_method"] = prediction.get(
                "take_trade_calibration_method"
            )
        return prediction

    def _apply_target_bps_models(self, bundle: dict[str, Any], ctx: ScoringContext) -> dict[str, Any]:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        feature_snapshot = source_snapshot.get("feature_snapshot")
        prediction = self._target_bps_models.predict(
            signal_row=db_row,
            feature_snapshot=feature_snapshot if isinstance(feature_snapshot, dict) else None,
        )
        db_row["expected_return_bps"] = prediction.get("expected_return_bps")
        db_row["expected_mae_bps"] = prediction.get("expected_mae_bps")
        db_row["expected_mfe_bps"] = prediction.get("expected_mfe_bps")
        db_row["target_projection_models_json"] = prediction.get("target_projection_models_json") or []
        if isinstance(source_snapshot, dict):
            source_snapshot["target_projection_summary"] = prediction.get("target_projection_summary")
            source_snapshot["target_projection_adjusted"] = prediction.get("target_projection_adjusted")
            source_snapshot["target_projection_models"] = prediction.get("target_projection_models_json") or []
            source_snapshot["model_contract"] = build_model_contract_bundle(
                quality_issues=ctx.data_issues,
                active_models=extract_active_models_from_signal_row(db_row),
            )
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list) and prediction.get("target_projection_summary") is not None:
            comp_hist.append(
                {
                    "layer": "target_projection_models",
                    "expected_return_bps": prediction.get("expected_return_bps"),
                    "expected_mae_bps": prediction.get("expected_mae_bps"),
                    "expected_mfe_bps": prediction.get("expected_mfe_bps"),
                    "summary": prediction.get("target_projection_summary"),
                    "cost_adjustment": prediction.get("target_projection_adjusted"),
                    "models": prediction.get("target_projection_models_json") or [],
                }
            )
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["expected_return_bps"] = prediction.get("expected_return_bps")
            event_payload["expected_mae_bps"] = prediction.get("expected_mae_bps")
            event_payload["expected_mfe_bps"] = prediction.get("expected_mfe_bps")
        return prediction

    def _apply_uncertainty_policy(
        self,
        bundle: dict[str, Any],
        ctx: ScoringContext,
        *,
        take_trade_prediction: dict[str, Any],
        target_projection: dict[str, Any],
    ) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        assessment = assess_model_uncertainty(
            ctx=ctx,
            settings=self._settings,
            signal_row=db_row,
            take_trade_prediction=take_trade_prediction,
            target_projection=target_projection,
        )
        prior_do_not_trade = bool(db_row.get("rejection_state")) or str(
            db_row.get("trade_action") or ""
        ).strip().lower() == "do_not_trade"
        unc_lane = assessment["uncertainty_execution_lane"]
        unc_phase = assessment["uncertainty_gate_phase"]
        unc_lane_reasons = list(assessment.get("uncertainty_lane_reasons_json") or [])
        event_phase = unc_phase
        if prior_do_not_trade:
            unc_lane = None
            unc_lane_reasons = []
            event_phase = "full"
        db_row["uncertainty_execution_lane"] = unc_lane
        db_row["uncertainty_gate_phase"] = unc_phase
        db_row["model_uncertainty_0_1"] = assessment["model_uncertainty_0_1"]
        db_row["shadow_divergence_0_1"] = assessment["shadow_divergence_0_1"]
        db_row["model_ood_score_0_1"] = assessment["model_ood_score_0_1"]
        db_row["model_ood_alert"] = assessment["model_ood_alert"]
        db_row["uncertainty_effective_for_leverage_0_1"] = assessment[
            "uncertainty_effective_for_leverage_0_1"
        ]
        db_row["uncertainty_reasons_json"] = assessment["uncertainty_reasons_json"]
        db_row["ood_reasons_json"] = assessment["ood_reasons_json"]
        rj_unc = db_row.get("reasons_json")
        if isinstance(rj_unc, dict):
            rj_unc["uncertainty_components"] = assessment["uncertainty_components"]
            rj_unc["uncertainty_exit_execution_bias"] = assessment["exit_execution_bias"]
        db_row["trade_action"] = (
            "do_not_trade"
            if prior_do_not_trade or assessment["trade_action"] == "do_not_trade"
            else "allow_trade"
        )
        if assessment["abstention_reasons_json"]:
            merged = list(db_row.get("abstention_reasons_json") or [])
            for reason in assessment["abstention_reasons_json"]:
                if reason not in merged:
                    merged.append(reason)
            db_row["abstention_reasons_json"] = merged
        if db_row["trade_action"] == "do_not_trade":
            db_row["decision_state"] = "rejected"
            db_row["rejection_state"] = True
            db_row["signal_class"] = "warnung"
            existing_rejections = list(db_row.get("rejection_reasons_json") or [])
            for reason in db_row["abstention_reasons_json"]:
                if reason not in existing_rejections:
                    existing_rejections.append(reason)
            db_row["rejection_reasons_json"] = existing_rejections
        if isinstance(source_snapshot, dict):
            source_snapshot["uncertainty_assessment"] = assessment["uncertainty_assessment"]
            if not prior_do_not_trade:
                source_snapshot["uncertainty_gate"] = {
                    "policy_version": assessment.get("policy_version"),
                    "gate_phase": unc_phase,
                    "execution_lane": unc_lane,
                    "lane_reasons_json": unc_lane_reasons,
                }
            else:
                source_snapshot.pop("uncertainty_gate", None)
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append(
                {
                    "layer": "uncertainty_policy",
                    "policy_version": assessment.get("policy_version"),
                    "model_uncertainty_0_1": assessment["model_uncertainty_0_1"],
                    "uncertainty_effective_for_leverage_0_1": assessment[
                        "uncertainty_effective_for_leverage_0_1"
                    ],
                    "uncertainty_components": assessment["uncertainty_components"],
                    "model_ood_score_0_1": assessment["model_ood_score_0_1"],
                    "model_ood_alert": assessment["model_ood_alert"],
                    "shadow_divergence_0_1": assessment["shadow_divergence_0_1"],
                    "trade_action": db_row["trade_action"],
                    "abstention_reasons_json": assessment["abstention_reasons_json"],
                    "uncertainty_execution_lane": unc_lane,
                    "uncertainty_gate_phase": event_phase,
                    "uncertainty_lane_reasons_json": unc_lane_reasons,
                    "exit_execution_bias": assessment["exit_execution_bias"],
                }
            )
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["model_uncertainty_0_1"] = assessment["model_uncertainty_0_1"]
            event_payload["uncertainty_effective_for_leverage_0_1"] = assessment[
                "uncertainty_effective_for_leverage_0_1"
            ]
            event_payload["shadow_divergence_0_1"] = assessment["shadow_divergence_0_1"]
            event_payload["model_ood_score_0_1"] = assessment["model_ood_score_0_1"]
            event_payload["model_ood_alert"] = assessment["model_ood_alert"]
            event_payload["uncertainty_execution_lane"] = unc_lane
            event_payload["uncertainty_gate_phase"] = event_phase
            event_payload["uncertainty_lane_reasons_json"] = unc_lane_reasons
            event_payload["uncertainty_reasons_json"] = assessment["uncertainty_reasons_json"]
            event_payload["ood_reasons_json"] = assessment["ood_reasons_json"]
            event_payload["abstention_reasons_json"] = db_row["abstention_reasons_json"]
            event_payload["trade_action"] = db_row["trade_action"]
            event_payload["decision_state"] = db_row["decision_state"]
            event_payload["rejection_state"] = db_row["rejection_state"]
            event_payload["rejection_reasons_json"] = db_row["rejection_reasons_json"]
            if db_row["trade_action"] == "do_not_trade":
                event_payload["signal_class"] = "warnung"

    def _apply_hybrid_decision(self, bundle: dict[str, Any]) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        summary = assess_hybrid_decision(settings=self._settings, signal_row=db_row)
        db_row["decision_confidence_0_1"] = summary["decision_confidence_0_1"]
        db_row["decision_policy_version"] = summary["decision_policy_version"]
        db_row["allowed_leverage"] = summary["allowed_leverage"]
        db_row["recommended_leverage"] = summary["recommended_leverage"]
        db_row["leverage_policy_version"] = summary["leverage_policy_version"]
        db_row["leverage_cap_reasons_json"] = summary["leverage_cap_reasons_json"]
        db_row["decision_state"] = summary["decision_state"]
        db_row["trade_action"] = summary["trade_action"]
        hybrid_lane = summary.get("meta_trade_lane")
        merged_lane = merge_meta_trade_lanes(
            db_row.get("uncertainty_execution_lane"),
            hybrid_lane,
            trade_action_blocked=str(summary["trade_action"]).strip().lower() == "do_not_trade",
        )
        db_row["meta_trade_lane"] = merged_lane
        db_row["signal_class"] = summary["signal_class"]
        merged_abstention = list(db_row.get("abstention_reasons_json") or [])
        for reason in summary["abstention_reasons_json"]:
            if reason not in merged_abstention:
                merged_abstention.append(reason)
        db_row["abstention_reasons_json"] = merged_abstention
        if db_row["decision_state"] == "rejected":
            db_row["rejection_state"] = True
            merged_rejections = list(db_row.get("rejection_reasons_json") or [])
            for reason in db_row["abstention_reasons_json"]:
                if reason not in merged_rejections:
                    merged_rejections.append(reason)
            db_row["rejection_reasons_json"] = merged_rejections
        if isinstance(source_snapshot, dict):
            source_snapshot["hybrid_decision"] = summary["hybrid_decision"]
            source_snapshot["hybrid_decision"]["meta_trade_lane_hybrid_raw"] = hybrid_lane
            source_snapshot["hybrid_decision"]["meta_trade_lane"] = merged_lane
            decision_trace_id = stable_decision_trace_id(
                signal_id=str(db_row["signal_id"]),
                decision_policy_version=str(summary["decision_policy_version"]),
            )
            source_snapshot["decision_trace_id"] = decision_trace_id
            cc = source_snapshot.get("correlation_chain")
            if isinstance(cc, dict):
                cc = dict(cc)
                cc["decision_trace_id"] = decision_trace_id
                cc["hybrid_policy_version"] = str(summary["decision_policy_version"])
                source_snapshot["correlation_chain"] = cc
        reasons_json = db_row.get("reasons_json")
        if isinstance(reasons_json, dict):
            rg = (summary.get("hybrid_decision") or {}).get("risk_governor") or {}
            reasons_json["hybrid_decision"] = {
                "policy_version": summary["decision_policy_version"],
                "trade_action": summary["trade_action"],
                "meta_trade_lane": merged_lane,
                "meta_trade_lane_hybrid_raw": hybrid_lane,
                "decision_state": summary["decision_state"],
                "confidence_0_1": summary["decision_confidence_0_1"],
                "allowed_leverage": summary["allowed_leverage"],
                "recommended_leverage": summary["recommended_leverage"],
                "leverage_policy_version": summary["leverage_policy_version"],
                "leverage_cap_reasons_json": summary["leverage_cap_reasons_json"],
                "abstention_reasons_json": summary["abstention_reasons_json"],
                "risk_governor_version": rg.get("version"),
                "max_risk_exposure_fraction_0_1": rg.get("max_exposure_fraction_0_1"),
                "risk_exit_strategies_allowed_json": rg.get("exit_strategies_allowed_json"),
                "risk_governor_universal_hard_block_reasons_json": rg.get(
                    "universal_hard_block_reasons_json"
                )
                or [],
                "live_execution_block_reasons_json": summary.get(
                    "live_execution_block_reasons_json"
                )
                or [],
                "portfolio_risk_synthesis_json": summary.get("portfolio_risk_synthesis_json"),
                "execution_policy_scope_note_de": (
                    "Universal-Hard-Blocks gelten fuer Paper/Shadow/Live; "
                    "live_execution_block_reasons_json blockiert nur Echtgeld-Submit im Live-Broker "
                    "(wenn RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=true)."
                ),
            }
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append({"layer": "hybrid_decision", **summary["hybrid_decision"]})
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["decision_confidence_0_1"] = summary["decision_confidence_0_1"]
            event_payload["decision_policy_version"] = summary["decision_policy_version"]
            event_payload["allowed_leverage"] = summary["allowed_leverage"]
            event_payload["recommended_leverage"] = summary["recommended_leverage"]
            event_payload["execution_leverage_cap"] = summary.get("execution_leverage_cap")
            event_payload["mirror_leverage"] = summary.get("mirror_leverage")
            event_payload["unified_leverage_allocator_version"] = summary.get(
                "unified_leverage_allocator_version"
            )
            event_payload["leverage_policy_version"] = summary["leverage_policy_version"]
            event_payload["leverage_cap_reasons_json"] = summary["leverage_cap_reasons_json"]
            event_payload["decision_state"] = summary["decision_state"]
            event_payload["trade_action"] = summary["trade_action"]
            event_payload["meta_trade_lane"] = merged_lane
            event_payload["meta_trade_lane_hybrid_raw"] = hybrid_lane
            event_payload["signal_class"] = summary["signal_class"]
            event_payload["abstention_reasons_json"] = db_row["abstention_reasons_json"]
            event_payload["rejection_state"] = db_row["rejection_state"]
            event_payload["rejection_reasons_json"] = db_row["rejection_reasons_json"]
            event_payload["decision_trace_id"] = source_snapshot.get("decision_trace_id")
            event_payload["correlation_chain"] = source_snapshot.get("correlation_chain")
            event_payload["live_execution_block_reasons_json"] = summary.get(
                "live_execution_block_reasons_json"
            ) or []
            event_payload["portfolio_risk_synthesis_json"] = summary.get(
                "portfolio_risk_synthesis_json"
            )

    def _apply_online_drift_guard(self, bundle: dict[str, Any]) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        state = self._repo.fetch_online_drift_state()
        if not state:
            return
        action = str(state.get("effective_action") or "ok").strip().lower()
        od_meta = {
            "effective_action": action,
            "computed_at": state.get("computed_at"),
            "lookback_minutes": state.get("lookback_minutes"),
            "enable_online_drift_block": self._settings.enable_online_drift_block,
        }
        reasons_json = db_row.get("reasons_json")
        if isinstance(reasons_json, dict):
            reasons_json["online_drift"] = od_meta
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["online_drift_effective_action"] = action
            event_payload["online_drift_computed_at"] = state.get("computed_at")
            event_payload["online_drift_live_forbidden"] = action in ("shadow_only", "hard_block")
        if not self._settings.enable_online_drift_block:
            return
        block_hard = action == "hard_block"
        block_shadow_too = (
            action == "shadow_only" and self._settings.enable_online_drift_shadow_only_signal_hard_block
        )
        if not block_hard and not block_shadow_too:
            return
        db_row["trade_action"] = "do_not_trade"
        db_row["decision_state"] = "rejected"
        db_row["rejection_state"] = True
        db_row["signal_class"] = "warnung"
        merged = list(db_row.get("rejection_reasons_json") or [])
        tag = "online_drift_hard_block" if block_hard else "online_drift_shadow_only_signal_hard_block"
        if tag not in merged:
            merged.append(tag)
        db_row["rejection_reasons_json"] = merged
        abst = list(db_row.get("abstention_reasons_json") or [])
        if tag not in abst:
            abst.append(tag)
        db_row["abstention_reasons_json"] = abst
        if isinstance(source_snapshot, dict):
            source_snapshot["online_drift_block"] = {
                **od_meta,
                "breakdown": state.get("breakdown_json"),
            }
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append({"layer": "online_drift_guard", **od_meta})
        if isinstance(event_payload, dict):
            event_payload["trade_action"] = db_row["trade_action"]
            event_payload["decision_state"] = db_row["decision_state"]
            event_payload["rejection_state"] = db_row["rejection_state"]
            event_payload["signal_class"] = db_row["signal_class"]
            event_payload["rejection_reasons_json"] = db_row["rejection_reasons_json"]
            event_payload["abstention_reasons_json"] = db_row["abstention_reasons_json"]
            event_payload["online_drift_live_forbidden"] = True

    def _apply_specialist_stack(self, bundle: dict[str, Any]) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        if not isinstance(source_snapshot, dict):
            return
        instrument_raw = source_snapshot.get("instrument")
        if not isinstance(instrument_raw, dict):
            symbol = str(db_row.get("symbol") or "").strip().upper()
            if not symbol:
                return
            instrument = self._settings.instrument_identity(symbol=symbol)
        else:
            instrument = BitgetInstrumentIdentity.model_validate(instrument_raw)
        specialist_stack = build_specialist_stack(signal_row=db_row, instrument=instrument)
        source_snapshot["specialists"] = specialist_stack
        router_arb = specialist_stack.get("router_arbitration") or {}
        routed_action = str(router_arb.get("selected_trade_action") or "").strip().lower()
        prior_action = str(db_row.get("trade_action") or "").strip().lower()
        ensemble_mult = router_arb.get("ensemble_confidence_multiplier_0_1")
        try:
            ensemble_mult_f = float(ensemble_mult) if ensemble_mult is not None else 1.0
        except (TypeError, ValueError):
            ensemble_mult_f = 1.0
        if routed_action == "do_not_trade" and prior_action == "allow_trade":
            db_row["trade_action"] = "do_not_trade"
            if str(db_row.get("decision_state") or "").strip().lower() == "accepted":
                db_row["decision_state"] = "downgraded"
            db_row["signal_class"] = "warnung"
            db_row["recommended_leverage"] = None
            abst = list(db_row.get("abstention_reasons_json") or [])
            for r in router_arb.get("reasons") or []:
                if isinstance(r, str) and r.startswith("ensemble_") and r not in abst:
                    abst.append(r)
            for r in (specialist_stack.get("adversary_check") or {}).get("reasons") or []:
                if isinstance(r, str) and r.startswith("adversary_") and r not in abst:
                    abst.append(r)
            db_row["abstention_reasons_json"] = abst
        elif routed_action == "allow_trade" and ensemble_mult_f < 0.999:
            dc_raw = db_row.get("decision_confidence_0_1")
            try:
                dc = float(dc_raw) if dc_raw is not None else 0.6
            except (TypeError, ValueError):
                dc = 0.6
            db_row["decision_confidence_0_1"] = round(max(0.45, min(0.98, dc * ensemble_mult_f)), 6)
            abst = list(db_row.get("abstention_reasons_json") or [])
            tag = "ensemble_dissent_confidence_shrink"
            if tag not in abst:
                abst.append(tag)
            db_row["abstention_reasons_json"] = abst
        playbook_context = specialist_stack.get("playbook_context") or {}
        if isinstance(playbook_context, dict):
            source_snapshot["playbook_context"] = playbook_context
            db_row["playbook_id"] = playbook_context.get("selected_playbook_id")
            db_row["playbook_family"] = playbook_context.get("selected_playbook_family")
            db_row["playbook_decision_mode"] = playbook_context.get("decision_mode") or "playbookless"
            db_row["playbook_registry_version"] = playbook_context.get("registry_version")
            if not db_row.get("strategy_name"):
                db_row["strategy_name"] = playbook_context.get("recommended_strategy_name")
        self._logger.info(
            (
                "specialist_stack signal_id=%s router_id=%s routed_action=%s prior_action=%s "
                "playbook_id=%s meta_lane=%s dissent=%s operator_gate=%s stop_fragility=%s"
            ),
            db_row.get("signal_id"),
            router_arb.get("router_id"),
            routed_action or "",
            prior_action,
            db_row.get("playbook_id"),
            router_arb.get("selected_meta_trade_lane"),
            (specialist_stack.get("adversary_check") or {}).get("dissent_score_0_1")
            if isinstance(specialist_stack.get("adversary_check"), dict)
            else None,
            router_arb.get("operator_gate_required"),
            db_row.get("stop_fragility_0_1"),
        )
        reasons_json = db_row.get("reasons_json")
        if isinstance(reasons_json, dict):
            reasons_json["specialists"] = specialist_stack
            reasons_json["playbook"] = {
                "playbook_id": db_row.get("playbook_id"),
                "playbook_family": db_row.get("playbook_family"),
                "playbook_decision_mode": db_row.get("playbook_decision_mode"),
                "playbook_registry_version": db_row.get("playbook_registry_version"),
                "selection_reasons": list(playbook_context.get("selection_reasons") or []),
                "invalid_context_hits": list(playbook_context.get("invalid_context_hits") or []),
                "anti_pattern_hits": list(playbook_context.get("anti_pattern_hits") or []),
                "blacklist_hits": list(playbook_context.get("blacklist_hits") or []),
                "benchmark_rule_ids": list(playbook_context.get("benchmark_rule_ids") or []),
                "counterfactual_candidates": list(
                    playbook_context.get("counterfactual_candidates") or []
                ),
                "playbookless_reason": playbook_context.get("playbookless_reason"),
            }
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append(
                {
                    "layer": "specialist_router",
                    "ensemble_contract": specialist_stack.get("ensemble_contract"),
                    "ensemble_hierarchy": specialist_stack.get("ensemble_hierarchy"),
                    "specialist_proposals_all": specialist_stack.get("specialist_proposals_all"),
                    "base_model": specialist_stack.get("base_model"),
                    "family_specialist": specialist_stack["family_specialist"],
                    "product_margin_specialist": specialist_stack.get("product_margin_specialist"),
                    "liquidity_vol_cluster_specialist": specialist_stack.get(
                        "liquidity_vol_cluster_specialist"
                    ),
                    "regime_specialist": specialist_stack["regime_specialist"],
                    "playbook_specialist": specialist_stack["playbook_specialist"],
                    "symbol_specialist": specialist_stack.get("symbol_specialist"),
                    "adversary_check": specialist_stack.get("adversary_check"),
                    "router_arbitration": specialist_stack["router_arbitration"],
                }
            )
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["specialists"] = specialist_stack
            event_payload["playbook_id"] = db_row.get("playbook_id")
            event_payload["playbook_family"] = db_row.get("playbook_family")
            event_payload["playbook_decision_mode"] = db_row.get("playbook_decision_mode")
            event_payload["playbook_registry_version"] = db_row.get("playbook_registry_version")
            event_payload["strategy_name"] = db_row.get("strategy_name")
            event_payload["market_family"] = instrument.market_family
            event_payload["margin_account_mode"] = instrument.margin_account_mode
            event_payload["instrument"] = instrument.model_dump(mode="json")
            event_payload["trade_action"] = db_row.get("trade_action")
            event_payload["decision_state"] = db_row.get("decision_state")
            event_payload["decision_confidence_0_1"] = db_row.get("decision_confidence_0_1")
            event_payload["signal_class"] = db_row.get("signal_class")
            event_payload["abstention_reasons_json"] = db_row.get("abstention_reasons_json")
            event_payload["recommended_leverage"] = db_row.get("recommended_leverage")

        smc0 = source_snapshot.get("structured_market_context")
        if isinstance(smc0, dict) and self._settings.structured_market_context_enabled:
            refined = refine_structured_market_context_for_playbook(
                smc0,
                playbook_family=str(db_row.get("playbook_family") or ""),
                settings=self._settings,
            )
            source_snapshot["structured_market_context"] = refined
            hd2 = source_snapshot.get("hybrid_decision")
            if isinstance(hd2, dict):
                rg2 = hd2.get("risk_governor")
                if isinstance(rg2, dict):
                    merge_live_reasons_into_risk_governor(rg2, refined)
            if isinstance(comp_hist, list):
                po = refined.get("playbook_overlay")
                comp_hist.append(
                    {
                        "layer": "structured_market_context_playbook",
                        "playbook_overlay": po if isinstance(po, dict) else {},
                        "surprise_playbook_adjusted": refined.get(
                            "surprise_score_playbook_adjusted_0_1"
                        ),
                    }
                )
        if isinstance(event_payload, dict):
            smc_ep = source_snapshot.get("structured_market_context")
            if isinstance(smc_ep, dict):
                extra = smc_ep.get("live_execution_block_reasons_json") or []
                if isinstance(extra, list) and extra:
                    cur = list(event_payload.get("live_execution_block_reasons_json") or [])
                    for t in extra:
                        if isinstance(t, str) and t.strip() and t not in cur:
                            cur.append(t.strip())
                    event_payload["live_execution_block_reasons_json"] = cur
                event_payload["structured_market_context_summary"] = {
                    "version": smc_ep.get("version"),
                    "facets_active_json": smc_ep.get("facets_active_json"),
                    "surprise_score_0_1": smc_ep.get("surprise_score_0_1"),
                    "surprise_score_playbook_adjusted_0_1": smc_ep.get(
                        "surprise_score_playbook_adjusted_0_1"
                    ),
                    "instrument_context_key": smc_ep.get("instrument_context_key"),
                }

    def _apply_meta_decision_kernel(self, bundle: dict[str, Any]) -> None:
        db_row = bundle["db_row"]
        out = apply_meta_decision_kernel(settings=self._settings, db_row=db_row)
        db_row["meta_decision_action"] = out["meta_decision_action"]
        db_row["meta_decision_kernel_version"] = out["meta_decision_kernel_version"]
        db_row["meta_decision_bundle_json"] = out["meta_decision_bundle_json"]
        db_row["operator_override_audit_json"] = db_row.get("operator_override_audit_json")

        if out["kernel_forces_do_not_trade"]:
            db_row["trade_action"] = "do_not_trade"
            db_row["recommended_leverage"] = None
            if str(db_row.get("decision_state") or "").strip().lower() == "accepted":
                db_row["decision_state"] = "downgraded"
            db_row["signal_class"] = "warnung"
            db_row["meta_trade_lane"] = merge_meta_trade_lanes(
                db_row.get("meta_trade_lane"),
                None,
                trade_action_blocked=True,
            )
            abst = list(db_row.get("abstention_reasons_json") or [])
            for code in out["kernel_abstention_codes"]:
                if code not in abst:
                    abst.append(code)
            db_row["abstention_reasons_json"] = abst

        source_snapshot = db_row.get("source_snapshot_json")
        if isinstance(source_snapshot, dict):
            source_snapshot["meta_decision_kernel"] = dict(out["meta_decision_bundle_json"])
        reasons_json = db_row.get("reasons_json")
        if isinstance(reasons_json, dict):
            reasons_json["meta_decision_kernel"] = {
                "version": out["meta_decision_kernel_version"],
                "meta_decision_action": out["meta_decision_action"],
                "kernel_forces_do_not_trade": out["kernel_forces_do_not_trade"],
                "abstention_codes": out["kernel_abstention_codes"],
                "bundle": out["meta_decision_bundle_json"],
            }
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append(
                {
                    "layer": "meta_decision_kernel",
                    **dict(out["meta_decision_bundle_json"]),
                }
            )
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["meta_decision_action"] = out["meta_decision_action"]
            event_payload["meta_decision_kernel_version"] = out["meta_decision_kernel_version"]
            event_payload["trade_action"] = db_row["trade_action"]
            event_payload["meta_trade_lane"] = db_row.get("meta_trade_lane")
            event_payload["decision_state"] = db_row.get("decision_state")
            event_payload["signal_class"] = db_row.get("signal_class")
            event_payload["abstention_reasons_json"] = db_row.get("abstention_reasons_json")

    def _apply_unified_exit_plan(self, bundle: dict[str, Any]) -> None:
        """Gleicher Exit-Plan fuer Paper/Shadow/Live (serialisiert, broker-agnostisch)."""
        db_row = bundle["db_row"]
        rj = db_row.get("reasons_json")
        if not isinstance(rj, dict):
            return
        dcf = rj.get("decision_control_flow")
        edb = dcf.get("end_decision_binding") if isinstance(dcf, dict) else None
        snap = db_row.get("source_snapshot_json")
        if not isinstance(snap, dict):
            return
        fs = snap.get("feature_snapshot")
        pf = fs.get("primary_tf") if isinstance(fs, dict) else None
        if not isinstance(pf, dict):
            pf = None
        sba = snap.get("stop_budget_assessment")
        if not isinstance(sba, dict):
            sba = {}
        plan = build_unified_exit_plan(
            signal_row=db_row,
            end_decision_binding=edb if isinstance(edb, dict) else None,
            stop_budget_assessment=sba,
            primary_feature=pf,
        )
        snap["unified_exit_plan"] = plan
        rj["unified_exit_plan"] = plan
        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append({"layer": "unified_exit_plan", **plan})
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["unified_exit_plan_version"] = plan.get("version")

    def _finalize_decision_control_flow(self, bundle: dict[str, Any]) -> None:
        attach_decision_control_flow_to_bundle(bundle)
        db_row = bundle["db_row"]
        rj = db_row.get("reasons_json")
        flow = rj.get("decision_control_flow") if isinstance(rj, dict) else None
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict) and isinstance(flow, dict):
            event_payload["decision_pipeline_version"] = flow.get("pipeline_version")
            event_payload["decision_control_flow"] = flow

    def _apply_catalog_resolution(self, bundle: dict[str, Any], symbol: str) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        event_payload = bundle.get("event_payload")
        try:
            family = self._settings.bitget_market_family
            metadata = self._metadata_service.resolve_metadata(
                symbol=symbol,
                market_family=family,
                product_type=(
                    self._settings.bitget_product_type if family == "futures" else None
                ),
                margin_account_mode=(
                    self._settings.bitget_margin_account_mode if family == "margin" else None
                ),
                refresh_if_missing=False,
            )
        except Exception as exc:
            if isinstance(source_snapshot, dict):
                source_snapshot["catalog_resolution_error"] = str(exc)
            reasons = list(db_row.get("rejection_reasons_json") or [])
            if "instrument_unknown" not in reasons:
                reasons.append("instrument_unknown")
            db_row["rejection_reasons_json"] = reasons
            db_row["abstention_reasons_json"] = list(
                dict.fromkeys(list(db_row.get("abstention_reasons_json") or []) + ["instrument_unknown"])
            )
            db_row["trade_action"] = "do_not_trade"
            db_row["decision_state"] = "rejected"
            db_row["rejection_state"] = True
            db_row["signal_class"] = "warnung"
            if isinstance(event_payload, dict):
                event_payload["catalog_resolution_error"] = str(exc)
            return
        instrument = metadata.entry.identity()
        if isinstance(source_snapshot, dict):
            source_snapshot["instrument"] = metadata.entry.model_dump(mode="json")
            source_snapshot["instrument_metadata_snapshot_id"] = metadata.snapshot_id
            source_snapshot["instrument_metadata"] = metadata.model_dump(mode="json")
            source_snapshot["canonical_instrument_id"] = metadata.canonical_instrument_id
        db_row["market_family"] = instrument.market_family
        if isinstance(event_payload, dict):
            event_payload["market_family"] = instrument.market_family
            event_payload["margin_account_mode"] = instrument.margin_account_mode
            event_payload["instrument"] = metadata.entry.model_dump(mode="json")
            event_payload["instrument_metadata_snapshot_id"] = metadata.snapshot_id
            event_payload["instrument_metadata"] = metadata.model_dump(mode="json")
            event_payload["canonical_instrument_id"] = metadata.canonical_instrument_id

    def _resolve_context_instrument(
        self,
        symbol: str,
    ) -> tuple[BitgetInstrumentIdentity, str | None, list[str], dict[str, Any] | None]:
        fallback = self._settings.instrument_identity(symbol=symbol)
        try:
            metadata = self._metadata_service.resolve_metadata(
                symbol=symbol,
                market_family=self._settings.bitget_market_family,
                product_type=(
                    self._settings.bitget_product_type
                    if self._settings.bitget_market_family == "futures"
                    else None
                ),
                margin_account_mode=(
                    self._settings.bitget_margin_account_mode
                    if self._settings.bitget_market_family == "margin"
                    else None
                ),
                refresh_if_missing=False,
            )
        except Exception:
            return fallback, None, ["signal_context_metadata_unavailable"], None
        entry = metadata.entry
        exec_meta: dict[str, Any] = {
            "canonical_instrument_id": metadata.canonical_instrument_id,
            "price_tick_size": entry.price_tick_size,
            "price_precision": entry.price_precision,
            "leverage_max_catalog": entry.leverage_max,
            "min_notional_quote": entry.min_notional_quote,
        }
        return metadata.entry.identity(), metadata.canonical_instrument_id, [], exec_meta

    def _sync_event_unified_leverage(self, bundle: dict[str, Any]) -> None:
        ep = bundle.get("event_payload")
        snap = bundle["db_row"].get("source_snapshot_json")
        if not isinstance(ep, dict) or not isinstance(snap, dict):
            return
        hd = snap.get("hybrid_decision")
        if not isinstance(hd, dict):
            return
        la = hd.get("leverage_allocator")
        if not isinstance(la, dict):
            return
        u = la.get("unified_leverage_allocation")
        if isinstance(u, dict):
            ep["execution_leverage_cap"] = u.get("execution_leverage_cap")
            ep["mirror_leverage"] = u.get("mirror_leverage")
            ep["unified_leverage_allocator_version"] = u.get("version")

    def _apply_stop_budget_policy(self, bundle: dict[str, Any], ctx: ScoringContext) -> None:
        db_row = bundle["db_row"]
        source_snapshot = db_row.get("source_snapshot_json") or {}
        if not isinstance(source_snapshot, dict):
            return
        assessment = assess_stop_budget_policy(
            settings=self._settings,
            signal_row=db_row,
            drawings=list(ctx.drawings),
            last_close=ctx.last_close,
            primary_feature=ctx.primary_feature,
            instrument_execution=ctx.instrument_execution_meta,
            stop_trigger_type=str(self._settings.signal_default_stop_trigger_type),
        )
        source_snapshot["stop_budget_assessment"] = assessment
        reasons_json = db_row.get("reasons_json")
        if isinstance(reasons_json, dict):
            reasons_json["stop_budget_assessment"] = assessment
        db_row["stop_distance_pct"] = assessment.get("stop_distance_pct")
        db_row["stop_budget_max_pct_allowed"] = assessment.get("stop_budget_max_pct_allowed")
        db_row["stop_min_executable_pct"] = assessment.get("stop_min_executable_pct")
        db_row["stop_to_spread_ratio"] = assessment.get("stop_to_spread_ratio")
        db_row["stop_quality_0_1"] = assessment.get("stop_quality_0_1")
        db_row["stop_executability_0_1"] = assessment.get("stop_executability_0_1")
        db_row["stop_fragility_0_1"] = assessment.get("stop_fragility_0_1")
        oc0 = str(assessment.get("outcome") or "")
        db_row["stop_budget_policy_version"] = (
            STOP_BUDGET_POLICY_VERSION if oc0 not in ("", "skipped") else None
        )

        outcome = oc0
        if outcome == "leverage_reduced":
            new_l = assessment.get("leverage_after")
            try:
                nl = int(new_l) if new_l is not None else None
            except (TypeError, ValueError):
                nl = None
            if nl is not None and nl >= self._settings.risk_allowed_leverage_min:
                db_row["allowed_leverage"] = nl
                rec = db_row.get("recommended_leverage")
                try:
                    rec_i = int(rec) if rec is not None else nl
                except (TypeError, ValueError):
                    rec_i = nl
                db_row["recommended_leverage"] = min(rec_i, nl)
                caps = list(db_row.get("leverage_cap_reasons_json") or [])
                for tag in assessment.get("gate_reasons_json") or []:
                    if tag not in caps:
                        caps.append(tag)
                db_row["leverage_cap_reasons_json"] = caps
                hd = source_snapshot.get("hybrid_decision")
                if isinstance(hd, dict):
                    hd = dict(hd)
                    hd["allowed_leverage"] = nl
                    hd["recommended_leverage"] = db_row["recommended_leverage"]
                    la = hd.get("leverage_allocator")
                    if isinstance(la, dict):
                        la = dict(la)
                        la["allowed_leverage"] = nl
                        la["recommended_leverage"] = db_row["recommended_leverage"]
                        hd["leverage_allocator"] = la
                    source_snapshot["hybrid_decision"] = hd

        if outcome == "blocked" and str(db_row.get("trade_action") or "") == "allow_trade":
            db_row["trade_action"] = "do_not_trade"
            grx = [str(x) for x in (assessment.get("gate_reasons_json") or [])]
            structural = any("stop_zone_not_protective" in x for x in grx)
            if structural:
                db_row["decision_state"] = "rejected"
                db_row["rejection_state"] = True
            elif str(db_row.get("decision_state") or "") != "rejected":
                db_row["decision_state"] = "downgraded"
            db_row["signal_class"] = "warnung"
            abst = list(db_row.get("abstention_reasons_json") or [])
            for tag in ("stop_budget_blocked", *(assessment.get("gate_reasons_json") or [])):
                if tag not in abst:
                    abst.append(tag)
            db_row["abstention_reasons_json"] = abst
            if assessment.get("gate_reasons_json"):
                reasons = list(db_row.get("rejection_reasons_json") or [])
                for tag in assessment["gate_reasons_json"]:
                    if tag not in reasons:
                        reasons.append(tag)
                db_row["rejection_reasons_json"] = reasons

        comp_hist = db_row.get("signal_components_history_json")
        if isinstance(comp_hist, list):
            comp_hist.append({"layer": "stop_budget_policy", **assessment})
        event_payload = bundle.get("event_payload")
        if isinstance(event_payload, dict):
            event_payload["stop_budget_outcome"] = assessment.get("outcome")
            event_payload["stop_distance_pct"] = assessment.get("stop_distance_pct")
            event_payload["stop_budget_max_pct_allowed"] = assessment.get(
                "stop_budget_max_pct_allowed"
            )
            event_payload["stop_min_executable_pct"] = assessment.get("stop_min_executable_pct")
            event_payload["stop_to_spread_ratio"] = assessment.get("stop_to_spread_ratio")
            event_payload["stop_quality_0_1"] = assessment.get("stop_quality_0_1")
            event_payload["stop_executability_0_1"] = assessment.get("stop_executability_0_1")
            event_payload["stop_fragility_0_1"] = assessment.get("stop_fragility_0_1")
            event_payload["stop_budget_policy_version"] = db_row.get("stop_budget_policy_version")
            event_payload["allowed_leverage"] = db_row.get("allowed_leverage")
            event_payload["recommended_leverage"] = db_row.get("recommended_leverage")
            event_payload["trade_action"] = db_row.get("trade_action")
            event_payload["abstention_reasons_json"] = db_row.get("abstention_reasons_json")
        refresh_unified_leverage_allocation_in_snapshot(db_row=db_row, settings=self._settings)
        self._sync_event_unified_leverage(bundle)
