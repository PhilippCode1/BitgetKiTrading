"""
Harte Ablehnungs- / Downgrade-Regeln (Pflicht).
"""

from __future__ import annotations

from dataclasses import dataclass
from shared_py.signal_contracts import DecisionState

from signal_engine.config import SignalEngineSettings
from signal_engine.models import ScoringContext
from signal_engine.news_compat import news_sentiment_as_float
from signal_engine.scoring.risk_score import _first_geometry, _reward_risk_ratio


@dataclass
class RejectionOutcome:
    decision_state: DecisionState
    rejection_state: bool
    rejection_reasons: list[str]


def apply_rejections(
    ctx: ScoringContext,
    settings: SignalEngineSettings,
    *,
    composite: float,
    structure_score: float,
    multi_tf_score: float,
    risk_score: float,
    proposed_direction: str,
    layer_flags: list[str],
    structured_rejection_soft: list[str] | None = None,
    structured_rejection_hard: list[str] | None = None,
) -> RejectionOutcome:
    reasons: list[str] = []
    if not settings.signal_rejection_enabled:
        return RejectionOutcome("accepted", False, [])

    for issue in ctx.data_issues:
        if issue not in reasons:
            reasons.append(issue)

    if ctx.primary_feature is None:
        reasons.append("missing_primary_features")
    if ctx.structure_state is None:
        reasons.append("missing_structure_state")

    now = ctx.analysis_ts_ms
    feat = ctx.primary_feature
    if feat is not None:
        ct = int(feat.get("computed_ts_ms") or 0)
        if ct > 0 and now - ct > settings.signal_max_data_age_ms:
            reasons.append("stale_feature_data")
        spread_bps = _feature_float(feat, "spread_bps")
        if spread_bps is not None and spread_bps > settings.signal_max_spread_bps:
            reasons.append("spread_too_wide")
        execution_cost_bps = _feature_float(feat, "execution_cost_bps")
        if execution_cost_bps is not None and execution_cost_bps > settings.signal_max_execution_cost_bps:
            reasons.append("execution_cost_too_high")
        funding_rate_bps = _feature_float(feat, "funding_rate_bps")
        if funding_rate_bps is not None and proposed_direction in ("long", "short"):
            adverse_funding = funding_rate_bps if proposed_direction == "long" else -funding_rate_bps
            if adverse_funding > settings.signal_max_adverse_funding_bps:
                reasons.append("adverse_funding_too_high")
        liquidity_source = str(feat.get("liquidity_source") or "").strip()
        if liquidity_source and liquidity_source != "orderbook_levels":
            reasons.append("liquidity_context_fallback")

    if "recent_false_breakout" in layer_flags:
        reasons.append("false_breakout_warning")

    if risk_score < settings.signal_min_risk_score:
        reasons.append("risk_score_below_minimum")

    stop = _first_geometry(ctx.drawings, "stop_zone")
    targets = [d for d in ctx.drawings if d.get("type") == "target_zone"]
    rr = _reward_risk_ratio(ctx.last_close, stop, targets)
    if rr is not None and rr < settings.signal_min_reward_risk:
        reasons.append("reward_risk_below_minimum")

    if stop is None:
        reasons.append("stop_zone_unusable")

    if (
        proposed_direction in ("long", "short")
        and structure_score < settings.signal_min_structure_score_for_directional
    ):
        reasons.append("structure_too_weak_for_directional")

    if (
        proposed_direction in ("long", "short")
        and multi_tf_score < settings.signal_min_multi_tf_score_for_directional
    ):
        reasons.append("multi_timeframe_conflict")

    # News-Schock gegen Richtung (heuristisch, regelbasierte Relevanz aus DB;
    # LLM kann Relevanz nur innerhalb NEWS_SCORE_MAX_LLM_DELTA verschieben).
    if (
        settings.signal_news_shock_rejection_enabled
        and ctx.news_row
        and proposed_direction in ("long", "short")
    ):
        sent = news_sentiment_as_float(ctx.news_row.get("sentiment"))
        rel = ctx.news_row.get("relevance_score")
        if sent is not None and rel is not None:
            s = float(sent)
            r = float(rel)
            if r > 60 and s < -0.35 and proposed_direction == "long":
                reasons.append("news_shock_against_long")
            if r > 60 and s > 0.35 and proposed_direction == "short":
                reasons.append("news_shock_against_short")

    if "momentum_vs_structure_up" in layer_flags or "momentum_vs_structure_down" in layer_flags:
        if composite > 60:
            reasons.append("momentum_structure_friction")

    for bucket in (structured_rejection_soft, structured_rejection_hard):
        if not bucket:
            continue
        for raw in bucket:
            if isinstance(raw, str):
                tag = raw.strip()
                if tag and tag not in reasons:
                    reasons.append(tag)

    # Entscheidung
    hard = {
        "missing_primary_features",
        "missing_structure_state",
        "missing_last_close",
        "stale_feature_data",
        "invalid_primary_feature_contract",
        "primary_feature_schema_mismatch",
        "structure_state_from_future",
        "stale_structure_state",
        "invalid_last_close",
        "drawing_state_from_future",
        "stale_drawing_data",
        "stop_zone_unusable",
        "missing_liquidity_context",
        "liquidity_context_fallback",
        "stale_orderbook_feature_data",
        "missing_spread_feature",
        "missing_execution_cost_feature",
        "missing_slippage_proxy",
        "missing_funding_context",
        "missing_funding_feature",
        "stale_funding_feature_data",
        "missing_open_interest_context",
        "missing_open_interest_feature",
        "missing_open_interest_delta",
        "stale_open_interest_feature_data",
        "spread_too_wide",
        "execution_cost_too_high",
        "adverse_funding_too_high",
        "context_hard_event_veto_long",
        "context_hard_event_veto_short",
    }
    hit_hard = [x for x in reasons if x in hard]

    if hit_hard:
        return RejectionOutcome("rejected", True, reasons)

    if len(reasons) >= 3:
        return RejectionOutcome("rejected", True, reasons)

    if reasons:
        return RejectionOutcome("downgraded", False, reasons)

    return RejectionOutcome("accepted", False, [])


def _feature_float(row: dict[str, object], field: str) -> float | None:
    value = row.get(field)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
