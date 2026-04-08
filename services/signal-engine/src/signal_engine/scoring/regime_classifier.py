from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared_py.regime_engine import RegimeEngineInputs, RegimeEngineResult, classify_regime

from signal_engine.models import ScoringContext


@dataclass(frozen=True)
class RegimeAssessment:
    market_regime: str
    regime_state: str
    regime_bias: str
    regime_confidence_0_1: float
    regime_substate: str
    regime_transition_state: str
    regime_transition_reasons_json: list[str]
    regime_persistence_bars: int
    regime_reasons_json: list[str]
    regime_snapshot: dict[str, Any]


def _context_to_inputs(
    ctx: ScoringContext,
    *,
    news_shock_feature_enabled: bool,
) -> RegimeEngineInputs:
    return RegimeEngineInputs(
        timeframe=ctx.timeframe,
        analysis_ts_ms=ctx.analysis_ts_ms,
        market_family=ctx.instrument.market_family if ctx.instrument else None,
        canonical_instrument_id=ctx.canonical_instrument_id,
        previous_regime_snapshot=ctx.previous_regime_snapshot,
        structure_state=ctx.structure_state,
        structure_events=list(ctx.structure_events),
        primary_feature=ctx.primary_feature,
        features_by_tf=ctx.features_by_tf,
        news_row=ctx.news_row,
        news_shock_feature_enabled=news_shock_feature_enabled,
    )


def _result_to_assessment(res: RegimeEngineResult) -> RegimeAssessment:
    return RegimeAssessment(
        market_regime=res.market_regime,
        regime_state=res.regime_state,
        regime_bias=res.regime_bias,
        regime_confidence_0_1=res.regime_confidence_0_1,
        regime_substate=res.regime_substate,
        regime_transition_state=res.regime_transition_state,
        regime_transition_reasons_json=res.regime_transition_reasons_json,
        regime_persistence_bars=res.regime_persistence_bars,
        regime_reasons_json=res.regime_reasons_json,
        regime_snapshot=res.regime_snapshot,
    )


def classify_market_regime(
    ctx: ScoringContext,
    *,
    news_shock_feature_enabled: bool = True,
) -> RegimeAssessment:
    """Delegiert auf shared_py.regime_engine fuer Training/Inferenz-Paritaet."""
    inp = _context_to_inputs(ctx, news_shock_feature_enabled=news_shock_feature_enabled)
    return _result_to_assessment(classify_regime(inp))
