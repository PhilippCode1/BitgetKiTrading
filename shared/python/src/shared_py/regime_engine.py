"""
Kanonische Markt-Regime-Engine.

Gleiche Implementierung fuer Online-Inferenz (Signal-Engine) und fuer
Offline-Replays aus gespeicherten Features/Strukturdaten — solange die
Eingaben identisch sind, ist das Ergebnis bit-identisch (deterministisch).

Es gibt zwei Ebenen:
- `market_regime`: kompakte Grobklasse fuer bestehende Contracts
- `regime_state`: family-aware Feingranularitaet fuer Routing und Audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from shared_py.regime_policy import (
    REGIME_ONTOLOGY_VERSION,
    REGIME_ROUTING_POLICY_VERSION,
    REGIME_STATE_VALUES,
)

REGIME_ENGINE_VERSION = "3.0.1"

TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
}

# Schwellen — bewusst konservativ; siehe docs/regime_engine.md
_DISLOCATION_VOL_Z_ABS = 2.0
_DISLOCATION_ATRP_ABS = 0.18
_DISLOCATION_VOL_COST_BPS = 12.0
_DISLOCATION_SPREAD_BPS = 10.0
_DISLOCATION_EXEC_COST_BPS = 20.0
_DISLOCATION_OI_CHANGE_ABS = 10.0
_DISLOCATION_FUNDING_BPS_ABS = 14.0
_FUNDING_STRESS_FOR_COMBO = 12.0
_NEWS_RELEVANCE_SHOCK = 70.0
_NEWS_SENTIMENT_SHOCK_ABS = 0.35
_DISLOCATION_MIN_FOR_CLASS = 3
_DISLOCATION_COMBO_MIN = 2
_LOW_LIQUIDITY_SPREAD_BPS = {"spot": 12.0, "margin": 10.0, "futures": 8.0}
_LOW_LIQUIDITY_EXEC_COST_BPS = {"spot": 20.0, "margin": 18.0, "futures": 16.0}
_LOW_LIQUIDITY_DEPTH_RATIO = {"spot": 0.12, "margin": 0.15, "futures": 0.18}
_FUNDING_SKEW_BPS = 8.0
_BASIS_SKEW_BPS = 6.0
_NEWS_DRIVEN_RELEVANCE = 55.0
_NEWS_DRIVEN_SENTIMENT_ABS = 0.15
_RANGE_GRIND_RANGE_SCORE = 68.0
_RANGE_GRIND_ATRP = 0.10
_MEAN_REVERT_PRESSURE = 60.0
_EXPANSION_CLUSTER = 55.0
_EXPANSION_IMPULSE = 0.55
_DELIVERY_EVENT_WINDOW_MS = 1_800_000
_TRANSITION_CONFIRM_CONFIDENCE = 0.72
_IMMEDIATE_TRANSITION_STATES = {"shock", "low_liquidity", "delivery_sensitive"}


@dataclass
class RegimeEngineInputs:
    """Reines Eingabe-Bundle ohne Service-Abhaengigkeiten."""

    timeframe: str
    analysis_ts_ms: int
    structure_state: dict[str, Any] | None
    structure_events: list[dict[str, Any]]
    primary_feature: dict[str, Any] | None
    features_by_tf: dict[str, dict[str, Any] | None]
    news_row: dict[str, Any] | None
    news_shock_feature_enabled: bool = True
    market_family: str | None = None
    canonical_instrument_id: str | None = None
    previous_regime_snapshot: dict[str, Any] | None = None


@dataclass
class RegimeEngineResult:
    market_regime: str
    regime_state: str
    regime_bias: str
    regime_confidence_0_1: float
    regime_substate: str
    regime_transition_state: str
    regime_transition_reasons_json: list[str]
    regime_persistence_bars: int
    regime_reasons_json: list[str]
    regime_snapshot: dict[str, Any] = field(default_factory=dict)


def coerce_news_sentiment_float(value: Any) -> float | None:
    """Gleiche Semantik wie signal_engine.news_compat (dupliziert, um shared schlank zu halten)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    mapping = {
        "bullisch": 0.5,
        "bullish": 0.5,
        "baerisch": -0.5,
        "bärisch": -0.5,
        "bearish": -0.5,
        "neutral": 0.0,
        "mixed": 0.0,
        "unknown": 0.0,
    }
    if s in mapping:
        return mapping[s]
    return 0.0


def classify_regime(inp: RegimeEngineInputs) -> RegimeEngineResult:
    tf_ms = TIMEFRAME_TO_MS.get(inp.timeframe, 300_000)
    recent_window_ms = tf_ms * 3
    st = inp.structure_state or {}
    box = st.get("breakout_box_json")
    if not isinstance(box, dict):
        box = {}

    structure_trend = str(st.get("trend_dir") or "RANGE").upper()
    compression_flag = bool(st.get("compression_flag"))
    range_score = _feature_float(inp.primary_feature, "range_score")
    atrp = _feature_float(inp.primary_feature, "atrp_14")
    vol_z = _feature_float(inp.primary_feature, "vol_z_50")
    spread = _feature_float(inp.primary_feature, "spread_bps")
    execution_cost = _feature_float(inp.primary_feature, "execution_cost_bps")
    volatility_cost = _feature_float(inp.primary_feature, "volatility_cost_bps")
    oi_change = _feature_float(inp.primary_feature, "open_interest_change_pct")
    funding_bps = _feature_float(inp.primary_feature, "funding_rate_bps")
    basis_bps = _feature_float(inp.primary_feature, "basis_bps")
    impulse_ratio = _feature_float(inp.primary_feature, "impulse_body_ratio")
    ret_1 = _feature_float(inp.primary_feature, "ret_1")
    confluence = _feature_float(inp.primary_feature, "confluence_score_0_100")
    mean_reversion_pressure = _feature_float(inp.primary_feature, "mean_reversion_pressure_0_100")
    breakout_compression = _feature_float(inp.primary_feature, "breakout_compression_score_0_100")
    realized_vol_cluster = _feature_float(inp.primary_feature, "realized_vol_cluster_0_100")
    data_completeness = _feature_float(inp.primary_feature, "data_completeness_0_1")
    staleness_score = _feature_float(inp.primary_feature, "staleness_score_0_1")
    event_distance_ms = _feature_float(inp.primary_feature, "event_distance_ms")
    feature_quality_status = str(inp.primary_feature.get("feature_quality_status") or "").strip().lower()
    liquidity_source = str(inp.primary_feature.get("liquidity_source") or "").strip().lower()
    market_family = (
        str(inp.market_family or inp.primary_feature.get("market_family") or "unknown").strip().lower()
    )
    canonical_instrument_id = (
        str(inp.canonical_instrument_id or inp.primary_feature.get("canonical_instrument_id") or "").strip()
        or None
    )

    breakout_event = _latest_event(
        inp.structure_events, "BREAKOUT", max_age_ms=recent_window_ms, analysis_ts_ms=inp.analysis_ts_ms
    )
    false_breakout_event = _latest_event(
        inp.structure_events,
        "FALSE_BREAKOUT",
        max_age_ms=recent_window_ms,
        analysis_ts_ms=inp.analysis_ts_ms,
    )
    choch_count = _recent_event_count(
        inp.structure_events,
        "CHOCH",
        max_age_ms=recent_window_ms,
        analysis_ts_ms=inp.analysis_ts_ms,
    )

    breakout_side = _event_side(breakout_event)
    false_breakout_side = _event_side(false_breakout_event)
    prebreak_side = _prebreak_bias(box.get("prebreak_side"))
    pending_false = box.get("pending_false")
    pending_false_active = isinstance(pending_false, dict) and int(pending_false.get("bars_remaining") or 0) > 0

    mtf_alignment_ratio = _mtf_alignment_ratio(inp.features_by_tf, structure_trend)

    news = inp.news_row or {}
    news_relevance = _coerce_float(news.get("relevance_score"))
    news_sentiment = coerce_news_sentiment_float(news.get("sentiment"))
    impact_window = str(news.get("impact_window") or "").strip().lower()
    news_shock = (
        inp.news_shock_feature_enabled
        and news_relevance is not None
        and news_relevance >= _NEWS_RELEVANCE_SHOCK
        and news_sentiment is not None
        and abs(news_sentiment) >= _NEWS_SENTIMENT_SHOCK_ABS
    )
    if impact_window not in ("", "immediate", "short", "medium"):
        news_shock = False

    dislocation_signals = 0
    dislocation_reasons: list[str] = []
    if vol_z is not None and abs(vol_z) >= _DISLOCATION_VOL_Z_ABS:
        dislocation_signals += 1
        dislocation_reasons.append("vol_z_stress")
    if atrp is not None and abs(atrp) >= _DISLOCATION_ATRP_ABS:
        dislocation_signals += 1
        dislocation_reasons.append("atrp_stress")
    if volatility_cost is not None and volatility_cost >= _DISLOCATION_VOL_COST_BPS:
        dislocation_signals += 1
        dislocation_reasons.append("volatility_cost_stress")
    if spread is not None and spread >= _DISLOCATION_SPREAD_BPS:
        dislocation_signals += 1
        dislocation_reasons.append("spread_stress")
    if execution_cost is not None and execution_cost >= _DISLOCATION_EXEC_COST_BPS:
        dislocation_signals += 1
        dislocation_reasons.append("execution_cost_stress")
    if oi_change is not None and abs(oi_change) >= _DISLOCATION_OI_CHANGE_ABS:
        dislocation_signals += 1
        dislocation_reasons.append("oi_change_stress")
    if funding_bps is not None and abs(funding_bps) >= _DISLOCATION_FUNDING_BPS_ABS:
        dislocation_signals += 1
        dislocation_reasons.append("funding_bps_stress")

    funding_stress = funding_bps is not None and abs(funding_bps) >= _FUNDING_STRESS_FOR_COMBO

    market_regime = "chop"
    regime_bias = _trend_bias(structure_trend)
    reasons: list[str] = []
    confidence = 0.55
    substate = "chop_default"

    shock_led_micro = news_shock and dislocation_signals >= 1
    shock_pure_news = news_shock and dislocation_signals < 1
    dislocation_class = (not news_shock) and (
        dislocation_signals >= _DISLOCATION_MIN_FOR_CLASS
        or (dislocation_signals >= _DISLOCATION_COMBO_MIN and funding_stress)
    )

    if shock_led_micro or shock_pure_news:
        market_regime = "shock"
        regime_bias = _news_bias(news_sentiment) or breakout_side or regime_bias
        substate = "shock_news_led_micro" if shock_led_micro else "shock_news_event"
        reasons.append("news_shock_active")
        if shock_led_micro:
            reasons.append("news_plus_microstructure_confirmation")
        reasons.append(f"dislocation_signals={dislocation_signals}")
        if news_relevance is not None:
            reasons.append(f"news_relevance={news_relevance:.1f}")
        if news_sentiment is not None:
            reasons.append(f"news_sentiment={news_sentiment:.2f}")
        confidence = min(
            0.98,
            0.72
            + 0.08 * min(dislocation_signals, 3)
            + (0.1 if shock_led_micro else 0.04),
        )
    elif dislocation_class:
        market_regime = "dislocation"
        regime_bias = breakout_side or _trend_bias(structure_trend) or "neutral"
        substate = "dislocation_liquidity_microstructure"
        reasons.append("market_dislocation_active")
        reasons.append(f"dislocation_signals={dislocation_signals}")
        reasons.extend(dislocation_reasons[:6])
        confidence = min(0.96, 0.70 + 0.06 * min(dislocation_signals, 5))
    elif breakout_event is not None and false_breakout_event is None:
        market_regime = "breakout"
        regime_bias = breakout_side or prebreak_side or regime_bias or "neutral"
        substate = "breakout_fresh"
        reasons.append("fresh_breakout_event")
        if pending_false_active:
            substate = "breakout_pending_false_watch"
            reasons.append("pending_false_breakout_watch")
        if impulse_ratio is not None and impulse_ratio >= 0.55:
            reasons.append("impulse_body_supports_breakout")
        if vol_z is not None and vol_z >= 0.6:
            reasons.append("volume_supports_breakout")
        confidence = min(
            0.94,
            0.72
            + (0.06 if pending_false_active else 0.0)
            + (0.05 if impulse_ratio is not None and impulse_ratio >= 0.55 else 0.0)
            + (0.05 if vol_z is not None and vol_z >= 0.6 else 0.0)
            + (0.04 if confluence is not None and confluence >= 60.0 else 0.0),
        )
    elif compression_flag or (
        box
        and range_score is not None
        and range_score >= 68.0
        and atrp is not None
        and atrp <= 0.10
    ):
        market_regime = "compression"
        regime_bias = prebreak_side or regime_bias or "neutral"
        substate = "compression_structure_flag" if compression_flag else "compression_range_proxy"
        reasons.append("compression_state_active" if compression_flag else "compression_proxy_from_features")
        if box:
            reasons.append("breakout_box_present")
        if prebreak_side:
            reasons.append(f"prebreak_side={prebreak_side}")
        confidence = min(
            0.90,
            0.66
            + (0.10 if compression_flag else 0.0)
            + (0.06 if range_score is not None and range_score >= 75.0 else 0.0)
            + (0.04 if atrp is not None and atrp <= 0.07 else 0.0),
        )
    elif (
        structure_trend in ("UP", "DOWN")
        and choch_count < 2
        and false_breakout_event is None
        and (range_score is None or range_score < 68.0)
        and mtf_alignment_ratio >= 0.5
    ):
        market_regime = "trend"
        regime_bias = _trend_bias(structure_trend)
        substate = "trend_mtf_aligned" if mtf_alignment_ratio >= 0.75 else "trend_mtf_partial"
        reasons.append(f"structure_trend={structure_trend.lower()}")
        reasons.append(f"mtf_alignment_ratio={mtf_alignment_ratio:.2f}")
        if confluence is not None and confluence >= 60.0:
            reasons.append("confluence_supports_trend")
        confidence = min(
            0.92,
            0.64
            + (0.10 if mtf_alignment_ratio >= 0.75 else 0.0)
            + (0.06 if confluence is not None and confluence >= 60.0 else 0.0)
            + (0.04 if ret_1 is not None and abs(ret_1) >= 0.001 else 0.0),
        )
    else:
        market_regime = "chop"
        regime_bias = "neutral"
        substate = "chop_noisy_range"
        if false_breakout_event is not None:
            substate = "chop_false_breakout_churn"
            reasons.append("recent_false_breakout")
        if choch_count >= 2:
            substate = "chop_choch_churn"
            reasons.append("choch_churn")
        if structure_trend == "RANGE":
            reasons.append("structure_range")
        if range_score is not None and range_score >= 60.0:
            reasons.append("range_score_elevated")
        confidence = min(
            0.88,
            0.60
            + (0.08 if false_breakout_event is not None else 0.0)
            + (0.06 if choch_count >= 2 else 0.0)
            + (0.04 if structure_trend == "RANGE" else 0.0),
        )

    if market_regime != "shock" and news_shock:
        reasons.append("news_shock_context_present")
    if market_regime != "breakout" and breakout_event is not None:
        reasons.append("breakout_context_present")
    if market_regime != "compression" and compression_flag:
        reasons.append("compression_context_present")
    if market_regime != "chop" and false_breakout_side is not None:
        reasons.append(f"false_breakout_side={false_breakout_side}")
    if market_regime != "dislocation" and dislocation_signals >= 2 and not news_shock:
        reasons.append("latent_dislocation_context")

    raw_regime_state, regime_state_reasons, state_substate = _derive_regime_state(
        market_regime=market_regime,
        market_family=market_family,
        analysis_ts_ms=inp.analysis_ts_ms,
        structure_trend=structure_trend,
        choch_count=choch_count,
        news_relevance=news_relevance,
        news_sentiment=news_sentiment,
        news_shock=news_shock,
        spread=spread,
        execution_cost=execution_cost,
        liquidity_source=liquidity_source,
        depth_ratio=_feature_float(inp.primary_feature, "depth_to_bar_volume_ratio"),
        range_score=range_score,
        atrp=atrp,
        mean_reversion_pressure=mean_reversion_pressure,
        breakout_compression=breakout_compression,
        realized_vol_cluster=realized_vol_cluster,
        impulse_ratio=impulse_ratio,
        funding_bps=funding_bps,
        basis_bps=basis_bps,
        event_distance_ms=event_distance_ms,
        feature_quality_status=feature_quality_status,
        data_completeness=data_completeness,
        staleness_score=staleness_score,
    )
    effective_regime_state, transition_state, transition_reasons, persistence_bars, pending_state = (
        _apply_transition_policy(
            raw_regime_state=raw_regime_state,
            confidence=confidence,
            previous_snapshot=inp.previous_regime_snapshot,
            feature_quality_status=feature_quality_status,
            data_completeness=data_completeness,
            staleness_score=staleness_score,
        )
    )
    reasons.extend(regime_state_reasons)
    reasons.extend(transition_reasons)
    reasons = list(dict.fromkeys(reasons))

    snapshot = {
        "regime_engine_version": REGIME_ENGINE_VERSION,
        "regime_ontology_version": REGIME_ONTOLOGY_VERSION,
        "regime_policy_version": REGIME_ROUTING_POLICY_VERSION,
        "market_regime": market_regime,
        "regime_state": effective_regime_state,
        "raw_regime_state": raw_regime_state,
        "regime_substate": state_substate or substate,
        "regime_bias": regime_bias,
        "regime_confidence_0_1": round(confidence, 4),
        "regime_transition_state": transition_state,
        "regime_transition_reasons_json": list(dict.fromkeys(transition_reasons)),
        "regime_persistence_bars": persistence_bars,
        "pending_regime_state": pending_state,
        "market_family": market_family,
        "canonical_instrument_id": canonical_instrument_id,
        "structure_trend_dir": structure_trend,
        "compression_flag": compression_flag,
        "range_score": range_score,
        "atrp_14": atrp,
        "vol_z_50": vol_z,
        "spread_bps": spread,
        "execution_cost_bps": execution_cost,
        "volatility_cost_bps": volatility_cost,
        "funding_rate_bps": funding_bps,
        "open_interest_change_pct": oi_change,
        "impulse_body_ratio": impulse_ratio,
        "ret_1": ret_1,
        "confluence_score_0_100": confluence,
        "mtf_alignment_ratio": round(mtf_alignment_ratio, 4),
        "breakout_side": breakout_side,
        "prebreak_bias": prebreak_side,
        "pending_false_active": pending_false_active,
        "false_breakout_recent": false_breakout_event is not None,
        "choch_count_recent": choch_count,
        "news_relevance_score": news_relevance,
        "news_sentiment": news_sentiment,
        "news_impact_window": impact_window or None,
        "news_shock_active": news_shock,
        "feature_quality_status": feature_quality_status or None,
        "data_completeness_0_1": data_completeness,
        "staleness_score_0_1": staleness_score,
        "event_distance_ms": event_distance_ms,
        "basis_bps": basis_bps,
        "mean_reversion_pressure_0_100": mean_reversion_pressure,
        "breakout_compression_score_0_100": breakout_compression,
        "realized_vol_cluster_0_100": realized_vol_cluster,
        "liquidity_source": liquidity_source or None,
        "session_transition_label": _session_window_label(inp.analysis_ts_ms),
        "near_hourly_boundary": _near_hourly_boundary(inp.analysis_ts_ms),
        "dislocation_signal_count": dislocation_signals,
        "dislocation_signal_tags": dislocation_reasons,
        "recent_structure_event_types": [str(ev.get("type") or "") for ev in inp.structure_events[:8]],
        "reasons": reasons,
    }
    return RegimeEngineResult(
        market_regime=market_regime,
        regime_state=effective_regime_state,
        regime_bias=regime_bias,
        regime_confidence_0_1=round(confidence, 4),
        regime_substate=state_substate or substate,
        regime_transition_state=transition_state,
        regime_transition_reasons_json=list(dict.fromkeys(transition_reasons)),
        regime_persistence_bars=persistence_bars,
        regime_reasons_json=reasons,
        regime_snapshot=snapshot,
    )


def _feature_float(row: dict[str, Any] | None, field: str) -> float | None:
    if row is None:
        return None
    return _coerce_float(row.get(field))


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _latest_event(
    events: list[dict[str, Any]],
    event_type: str,
    *,
    max_age_ms: int,
    analysis_ts_ms: int,
) -> dict[str, Any] | None:
    for event in events:
        if str(event.get("type") or "") != event_type:
            continue
        try:
            ts_ms = int(event.get("ts_ms") or 0)
        except (TypeError, ValueError):
            ts_ms = 0
        if ts_ms <= 0:
            continue
        if analysis_ts_ms - ts_ms <= max_age_ms:
            return event
    return None


def _recent_event_count(
    events: list[dict[str, Any]],
    event_type: str,
    *,
    max_age_ms: int,
    analysis_ts_ms: int,
) -> int:
    total = 0
    for event in events:
        if str(event.get("type") or "") != event_type:
            continue
        try:
            ts_ms = int(event.get("ts_ms") or 0)
        except (TypeError, ValueError):
            continue
        if ts_ms > 0 and analysis_ts_ms - ts_ms <= max_age_ms:
            total += 1
    return total


def _event_side(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    details = event.get("details_json")
    if not isinstance(details, dict):
        return None
    raw = str(details.get("side") or "").strip().upper()
    if raw == "UP":
        return "long"
    if raw == "DOWN":
        return "short"
    return None


def _prebreak_bias(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if raw == "high":
        return "long"
    if raw == "low":
        return "short"
    return None


def _trend_bias(trend_dir: str) -> str:
    if trend_dir == "UP":
        return "long"
    if trend_dir == "DOWN":
        return "short"
    return "neutral"


def _news_bias(sentiment: float | None) -> str | None:
    if sentiment is None:
        return None
    if sentiment >= 0.2:
        return "long"
    if sentiment <= -0.2:
        return "short"
    return "neutral"


def _mtf_alignment_ratio(features_by_tf: dict[str, dict[str, Any] | None], structure_trend: str) -> float:
    want = 1 if structure_trend == "UP" else -1 if structure_trend == "DOWN" else 0
    if want == 0:
        return 0.0
    votes = 0
    aligned = 0
    for tf in ("15m", "1H", "4H"):
        row = features_by_tf.get(tf)
        if row is None:
            continue
        try:
            trend_dir = int(row.get("trend_dir") or 0)
        except (TypeError, ValueError):
            trend_dir = 0
        if trend_dir == 0:
            continue
        votes += 1
        if trend_dir == want:
            aligned += 1
    if votes == 0:
        return 0.0
    return aligned / votes


def _derive_regime_state(
    *,
    market_regime: str,
    market_family: str,
    analysis_ts_ms: int,
    structure_trend: str,
    choch_count: int,
    news_relevance: float | None,
    news_sentiment: float | None,
    news_shock: bool,
    spread: float | None,
    execution_cost: float | None,
    liquidity_source: str,
    depth_ratio: float | None,
    range_score: float | None,
    atrp: float | None,
    mean_reversion_pressure: float | None,
    breakout_compression: float | None,
    realized_vol_cluster: float | None,
    impulse_ratio: float | None,
    funding_bps: float | None,
    basis_bps: float | None,
    event_distance_ms: float | None,
    feature_quality_status: str,
    data_completeness: float | None,
    staleness_score: float | None,
) -> tuple[str, list[str], str]:
    reasons: list[str] = []
    session_label = _session_window_label(analysis_ts_ms)
    spread_limit = _LOW_LIQUIDITY_SPREAD_BPS.get(market_family, 10.0)
    exec_limit = _LOW_LIQUIDITY_EXEC_COST_BPS.get(market_family, 18.0)
    depth_min = _LOW_LIQUIDITY_DEPTH_RATIO.get(market_family, 0.15)
    low_liquidity = (
        (spread is not None and spread >= spread_limit)
        or (execution_cost is not None and execution_cost >= exec_limit)
        or (depth_ratio is not None and depth_ratio < depth_min)
        or (market_family == "futures" and liquidity_source and not liquidity_source.startswith("orderbook_levels"))
        or (staleness_score is not None and staleness_score >= 0.7)
    )
    delivery_sensitive = (
        market_family == "futures"
        and event_distance_ms is not None
        and event_distance_ms <= _DELIVERY_EVENT_WINDOW_MS
    )
    funding_skewed = market_family == "futures" and (
        (funding_bps is not None and abs(funding_bps) >= _FUNDING_SKEW_BPS)
        or (basis_bps is not None and abs(basis_bps) >= _BASIS_SKEW_BPS)
    )
    news_driven = (
        not news_shock
        and news_relevance is not None
        and news_relevance >= _NEWS_DRIVEN_RELEVANCE
        and news_sentiment is not None
        and abs(news_sentiment) >= _NEWS_DRIVEN_SENTIMENT_ABS
    )
    session_transition = session_label is not None or _near_hourly_boundary(analysis_ts_ms)
    range_grind = (
        structure_trend == "RANGE"
        and range_score is not None
        and range_score >= _RANGE_GRIND_RANGE_SCORE
        and atrp is not None
        and atrp <= _RANGE_GRIND_ATRP
    )
    mean_reverting = (
        mean_reversion_pressure is not None
        and mean_reversion_pressure >= _MEAN_REVERT_PRESSURE
    ) or (
        market_regime == "chop"
        and structure_trend == "RANGE"
        and range_score is not None
        and range_score >= 55.0
    )
    structural_churn = market_regime == "chop" and choch_count >= 2
    expansion = market_regime == "breakout" or (
        (impulse_ratio is not None and impulse_ratio >= _EXPANSION_IMPULSE)
        and (
            (realized_vol_cluster is not None and realized_vol_cluster >= _EXPANSION_CLUSTER)
            or (breakout_compression is not None and breakout_compression >= 60.0)
        )
    )

    state = "range_grind"
    substate = "range_grind_default"
    if market_regime == "shock":
        state = "shock"
        substate = "shock_news_event"
        reasons.append("state_from_market_regime_shock")
    elif low_liquidity and market_regime in {"dislocation", "breakout", "chop", "compression"}:
        state = "low_liquidity"
        substate = (
            "low_liquidity_dislocation_stack"
            if market_regime == "dislocation"
            else "low_liquidity_spread_depth"
        )
        reasons.append("state_from_liquidity_stress")
    elif delivery_sensitive:
        state = "delivery_sensitive"
        substate = "delivery_sensitive_event_window"
        reasons.append("state_from_near_event_window")
    elif funding_skewed:
        state = "funding_skewed"
        substate = "funding_skewed_basis_funding"
        reasons.append("state_from_funding_basis_skew")
    elif news_driven:
        state = "news_driven"
        substate = "news_driven_context"
        reasons.append("state_from_news_context")
    elif session_transition and market_regime in {"trend", "breakout", "compression", "chop"}:
        state = "session_transition"
        substate = f"session_transition_{session_label or 'hourly'}"
        reasons.append("state_from_session_window")
    elif expansion:
        state = "expansion"
        substate = "expansion_breakout_followthrough"
        reasons.append("state_from_expansion_context")
    elif market_regime == "compression":
        state = "compression"
        substate = "compression_pre_break"
        reasons.append("state_from_compression_context")
    elif market_regime == "trend":
        state = "trend"
        substate = "trend_structural_alignment"
        reasons.append("state_from_trend_context")
    elif range_grind:
        state = "range_grind"
        substate = "range_grind_balanced"
        reasons.append("state_from_range_grind_context")
    elif structural_churn:
        state = "mean_reverting"
        substate = "mean_reverting_choch_churn"
        reasons.append("state_from_structure_choch_churn")
    elif mean_reverting:
        state = "mean_reverting"
        substate = "mean_reverting_pressure"
        reasons.append("state_from_mean_reversion_context")
    if feature_quality_status and feature_quality_status != "ok":
        reasons.append("state_quality_degraded")
    if data_completeness is not None and data_completeness < 0.78:
        reasons.append("state_data_completeness_low")
    return state, reasons, substate


def _apply_transition_policy(
    *,
    raw_regime_state: str,
    confidence: float,
    previous_snapshot: dict[str, Any] | None,
    feature_quality_status: str,
    data_completeness: float | None,
    staleness_score: float | None,
) -> tuple[str, str, list[str], int, str | None]:
    prev = previous_snapshot if isinstance(previous_snapshot, dict) else {}
    prev_state = str(prev.get("effective_regime_state") or prev.get("regime_state") or "").strip().lower()
    prev_pending = str(prev.get("pending_regime_state") or "").strip().lower()
    prev_persistence = _coerce_int(prev.get("regime_persistence_bars")) or 1
    reasons: list[str] = []
    quality_fragile = (
        (feature_quality_status not in {"", "ok"})
        or (data_completeness is not None and data_completeness < 0.78)
        or (staleness_score is not None and staleness_score > 0.55)
    )
    if prev_state not in REGIME_STATE_VALUES:
        return raw_regime_state, "stable", ["transition_no_prior_state"], 1, None
    if raw_regime_state == prev_state:
        return raw_regime_state, "stable", [], min(prev_persistence + 1, 999), None
    if raw_regime_state in _IMMEDIATE_TRANSITION_STATES and confidence >= _TRANSITION_CONFIRM_CONFIDENCE:
        reasons.append("transition_immediate_regime")
        return raw_regime_state, "switch_immediate", reasons, 1, None
    if quality_fragile:
        reasons.append("transition_hold_due_quality")
        return prev_state, "sticky_hold", reasons, min(prev_persistence + 1, 999), raw_regime_state
    if prev_pending and prev_pending == raw_regime_state and confidence >= _TRANSITION_CONFIRM_CONFIDENCE:
        reasons.append("transition_confirmed_consecutive_candidate")
        return raw_regime_state, "switch_confirmed", reasons, 1, None
    reasons.append("transition_pending_confirmation")
    return prev_state, "entering", reasons, min(prev_persistence + 1, 999), raw_regime_state


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _session_window_label(analysis_ts_ms: int) -> str | None:
    dt = datetime.fromtimestamp(int(analysis_ts_ms) / 1000.0, tz=timezone.utc)
    minute_of_day = dt.hour * 60 + dt.minute
    windows = {
        "asia_open": 0,
        "europe_open": 7 * 60,
        "us_open": 13 * 60 + 30,
    }
    for label, anchor in windows.items():
        if abs(minute_of_day - anchor) <= 20:
            return label
    return None


def _near_hourly_boundary(analysis_ts_ms: int) -> bool:
    dt = datetime.fromtimestamp(int(analysis_ts_ms) / 1000.0, tz=timezone.utc)
    return dt.minute <= 5 or dt.minute >= 55
