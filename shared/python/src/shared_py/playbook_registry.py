from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared_py.regime_policy import RegimeState

MarketFamilyName = Literal["spot", "margin", "futures"]
PlaybookFamily = Literal[
    "trend_continuation",
    "breakout",
    "mean_reversion",
    "volatility_compression_expansion",
    "liquidity_sweep",
    "pullback",
    "range_rotation",
    "carry_funding",
    "news_shock",
    "session_open",
    "time_window_effect",
]
PlaybookDecisionMode = Literal["selected", "playbookless"]
PlaybookStopFamily = Literal[
    "structure_invalidation",
    "breakout_fail",
    "microstructure_invalidation",
    "volatility_budget",
    "event_cut",
    "funding_flip",
    "session_open_fail",
    "time_window_expiry",
    "liquidity_sweep_invalidation",
]
PlaybookExitFamily = Literal[
    "scale_out",
    "runner",
    "time_stop",
    "liquidity_target",
    "event_exit",
    "trend_hold",
    "mean_reversion_unwind",
    "mean_reversion_snapback",
    "funding_harvest",
    "basis_funding_unwind",
    "session_close",
    "volatility_trail",
    "news_risk_flatten",
    "trend_follow_runner",
]

PLAYBOOK_REGISTRY_VERSION = "1.1"
PLAYBOOK_DECISION_MODE_VALUES: tuple[str, ...] = ("selected", "playbookless")


def _stable_hash(obj: object) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class PlaybookLiquidityConstraints(BaseModel):
    max_spread_bps: float | None = None
    max_execution_cost_bps: float | None = None
    min_depth_to_bar_volume_ratio: float | None = None
    min_data_completeness_0_1: float = 0.7
    max_staleness_score_0_1: float = 0.65
    require_orderbook_context: bool = False


class PlaybookBenchmarkRule(BaseModel):
    benchmark_id: str
    comparison_class: str
    evaluation_focus: list[str] = Field(default_factory=list)
    minimum_samples: int = 30
    notes: str = ""

    @field_validator("benchmark_id", "comparison_class", "notes", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str:
        return str(value or "").strip()


class PlaybookDefinition(BaseModel):
    playbook_id: str
    playbook_family: PlaybookFamily
    title: str
    summary: str
    target_market_families: list[MarketFamilyName] = Field(default_factory=list)
    regime_suitability: list[RegimeState] = Field(default_factory=list)
    invalid_contexts: list[str] = Field(default_factory=list)
    preferred_stop_families: list[PlaybookStopFamily] = Field(default_factory=list)
    exit_families: list[PlaybookExitFamily] = Field(default_factory=list)
    minimum_liquidity: PlaybookLiquidityConstraints = Field(
        default_factory=PlaybookLiquidityConstraints
    )
    preferred_timeframes: list[str] = Field(default_factory=list)
    benchmark_rules: list[PlaybookBenchmarkRule] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    blacklist_criteria: list[str] = Field(default_factory=list)
    counterfactual_candidates: list[str] = Field(default_factory=list)
    preferred_strategy_name: str | None = None

    @field_validator(
        "playbook_id",
        "title",
        "summary",
        "preferred_strategy_name",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator(
        "regime_suitability",
        "invalid_contexts",
        "preferred_timeframes",
        "anti_patterns",
        "blacklist_criteria",
        "counterfactual_candidates",
        mode="before",
    )
    @classmethod
    def _normalize_list_of_text(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("playbook list fields muessen Listen sein")
        out: list[str] = []
        for item in value:
            normalized = str(item or "").strip()
            if normalized:
                out.append(normalized)
        return out


PLAYBOOK_REGISTRY: tuple[PlaybookDefinition, ...] = (
    PlaybookDefinition(
        playbook_id="trend_continuation_core",
        playbook_family="trend_continuation",
        title="Trendfortsetzung",
        summary="Momentum- und Strukturfortsetzung mit intakter MTF-Ausrichtung und ohne Event-Stress.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["trend", "expansion"],
        invalid_contexts=["shock", "dislocation", "counter_regime_high_confidence"],
        preferred_stop_families=["structure_invalidation", "volatility_budget"],
        exit_families=["scale_out", "trend_follow_runner", "runner", "trend_hold"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=18.0,
            max_execution_cost_bps=30.0,
            min_depth_to_bar_volume_ratio=0.18,
            min_data_completeness_0_1=0.75,
        ),
        preferred_timeframes=["5m", "15m", "1H", "4H"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="trend_continuation_vs_pullback_same_regime",
                comparison_class="same_family_same_regime_same_timeframe_bucket",
                evaluation_focus=["expected_return_bps", "stop_out_rate", "profit_factor"],
                minimum_samples=40,
                notes="Vergleiche Trendfortsetzung gegen Pullback-Varianten im Trendregime.",
            )
        ],
        anti_patterns=["late_trend_chase", "mtf_confluence_missing", "event_too_close"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["pullback_trend_reentry", "session_open_drive"],
        preferred_strategy_name="TrendContinuationStrategy",
    ),
    PlaybookDefinition(
        playbook_id="breakout_expansion",
        playbook_family="breakout",
        title="Ausbruch / Expansion",
        summary="Expansion nach Verdichtung oder Triggerbruch mit brauchbarer Ausfuehrungsqualitaet.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["expansion", "compression", "session_transition"],
        invalid_contexts=["shock", "range_rotation_without_compression"],
        preferred_stop_families=["breakout_fail", "volatility_budget"],
        exit_families=["scale_out", "runner", "liquidity_target"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=14.0,
            max_execution_cost_bps=24.0,
            min_depth_to_bar_volume_ratio=0.22,
            min_data_completeness_0_1=0.78,
        ),
        preferred_timeframes=["1m", "5m", "15m", "1H"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="breakout_vs_vol_compression_same_setup",
                comparison_class="same_family_same_regime_same_market_family",
                evaluation_focus=["expected_mfe_bps", "time_to_tp1_ms", "slippage_bps_entry"],
                minimum_samples=35,
                notes="Prueft, ob Expansion wirklich Folgedruck liefert oder nur Fehlausbruch ist.",
            )
        ],
        anti_patterns=["breakout_without_compression", "breakout_into_thin_book"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["vol_compression_expansion", "session_open_drive"],
        preferred_strategy_name="BreakoutBoxStrategy",
    ),
    PlaybookDefinition(
        playbook_id="mean_reversion_reclaim",
        playbook_family="mean_reversion",
        title="Mean Reversion",
        summary="Ruecklauf gegen kurzfristige Ueberdehnung mit intakter Liquiditaet und begrenztem Regimestress.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["mean_reverting", "range_grind", "low_liquidity"],
        invalid_contexts=["trend_acceleration", "shock", "event_too_close"],
        preferred_stop_families=["microstructure_invalidation", "volatility_budget"],
        exit_families=["mean_reversion_snapback", "scale_out", "mean_reversion_unwind", "time_stop"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=20.0,
            max_execution_cost_bps=28.0,
            min_depth_to_bar_volume_ratio=0.15,
            min_data_completeness_0_1=0.72,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="mean_reversion_vs_range_rotation",
                comparison_class="same_regime_same_market_family_same_timeframe_bucket",
                evaluation_focus=["win_rate", "expected_return_bps", "stop_out_rate"],
                minimum_samples=40,
                notes="Trennt reine Ruecklaeufe von Range-Rotation-Edges.",
            )
        ],
        anti_patterns=["fade_strong_trend", "mean_reversion_without_pressure"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["range_rotation_rotation", "liquidity_sweep_reversal"],
        preferred_strategy_name="MeanReversionMicroStrategy",
    ),
    PlaybookDefinition(
        playbook_id="vol_compression_expansion",
        playbook_family="volatility_compression_expansion",
        title="Volatility Compression/Expansion",
        summary="Vorbereitete Expansion aus komprimierter Struktur mit sauberem Orderflow und nicht-stalem Kontext.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["compression", "expansion"],
        invalid_contexts=["shock", "dislocation", "high_spread_expansion"],
        preferred_stop_families=["breakout_fail", "volatility_budget"],
        exit_families=["scale_out", "runner", "volatility_trail"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=12.0,
            max_execution_cost_bps=20.0,
            min_depth_to_bar_volume_ratio=0.2,
            min_data_completeness_0_1=0.8,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="compression_expansion_vs_breakout_followthrough",
                comparison_class="same_market_family_same_signal_class",
                evaluation_focus=["expected_mfe_bps", "time_to_tp1_ms", "profit_factor"],
                minimum_samples=35,
                notes="Hilft zu unterscheiden, ob Kompression eigenstaendig alpha liefert.",
            )
        ],
        anti_patterns=["compression_absent", "depth_imbalance_missing"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["breakout_expansion", "time_window_repricing"],
        preferred_strategy_name="BreakoutBoxStrategy",
    ),
    PlaybookDefinition(
        playbook_id="liquidity_sweep_reversal",
        playbook_family="liquidity_sweep",
        title="Liquidity Sweep",
        summary="Sweep-/Stop-Run-Konstellationen mit Ruecknahme und Mean-Reversion- oder Reclaim-Charakter.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["low_liquidity", "shock", "range_grind"],
        invalid_contexts=["shock", "thin_book_followthrough"],
        preferred_stop_families=["liquidity_sweep_invalidation", "microstructure_invalidation"],
        exit_families=["scale_out", "mean_reversion_unwind", "liquidity_target"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=22.0,
            max_execution_cost_bps=30.0,
            min_depth_to_bar_volume_ratio=0.12,
            min_data_completeness_0_1=0.72,
            require_orderbook_context=True,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="liquidity_sweep_vs_mean_reversion",
                comparison_class="same_family_same_regime_same_market_family",
                evaluation_focus=["slippage_bps_entry", "expected_return_bps", "time_to_stop_ms"],
                minimum_samples=30,
                notes="Sweep-Setups muessen bessere Entry-Qualitaet liefern als generische Mean-Reversion.",
            )
        ],
        anti_patterns=["sweep_without_reclaim", "book_depth_missing"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["mean_reversion_reclaim", "range_rotation_rotation"],
        preferred_strategy_name="MeanReversionMicroStrategy",
    ),
    PlaybookDefinition(
        playbook_id="pullback_trend_reentry",
        playbook_family="pullback",
        title="Pullback / Re-Entry",
        summary="Ruecksetzer in intaktem Trend mit begrenzter Gegenbewegung und klarer Fortsetzungslogik.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["trend", "session_transition"],
        invalid_contexts=["shock", "dislocation", "trend_broken"],
        preferred_stop_families=["structure_invalidation", "volatility_budget"],
        exit_families=["scale_out", "trend_follow_runner", "runner", "trend_hold"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=18.0,
            max_execution_cost_bps=26.0,
            min_depth_to_bar_volume_ratio=0.18,
            min_data_completeness_0_1=0.75,
        ),
        preferred_timeframes=["5m", "15m", "1H"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="pullback_vs_trend_continuation",
                comparison_class="same_regime_same_direction_same_market_family",
                evaluation_focus=["expected_mae_bps", "profit_factor", "stop_out_rate"],
                minimum_samples=35,
                notes="Pullback darf weniger adverse excursion zeigen als späte Trendfortsetzung.",
            )
        ],
        anti_patterns=["pullback_too_deep", "counter_regime_bias"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["trend_continuation_core", "range_rotation_rotation"],
        preferred_strategy_name="TrendContinuationStrategy",
    ),
    PlaybookDefinition(
        playbook_id="range_rotation_rotation",
        playbook_family="range_rotation",
        title="Range Rotation",
        summary="Rotation von Range-Rand zu Gegenseite ohne echte Trend- oder Event-Expansion.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["range_grind", "mean_reverting"],
        invalid_contexts=["trend", "breakout", "shock"],
        preferred_stop_families=["microstructure_invalidation", "volatility_budget"],
        exit_families=["scale_out", "mean_reversion_unwind", "time_stop"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=20.0,
            max_execution_cost_bps=28.0,
            min_depth_to_bar_volume_ratio=0.15,
            min_data_completeness_0_1=0.72,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="range_rotation_vs_mean_reversion",
                comparison_class="same_regime_same_market_family_same_timeframe_bucket",
                evaluation_focus=["win_rate", "time_to_tp1_ms", "expected_return_bps"],
                minimum_samples=35,
                notes="Range-Rotation soll nur in echten Balance-Zustaenden besser sein als generischer Fade.",
            )
        ],
        anti_patterns=["range_boundary_missing", "breakout_pressure_high"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["mean_reversion_reclaim", "liquidity_sweep_reversal"],
        preferred_strategy_name="MeanReversionMicroStrategy",
    ),
    PlaybookDefinition(
        playbook_id="carry_funding_capture",
        playbook_family="carry_funding",
        title="Carry / Funding",
        summary="Futures-only Konstellationen mit Funding-/Basis-Edge und klarer Event- oder Hold-Logik.",
        target_market_families=["futures"],
        regime_suitability=["funding_skewed", "delivery_sensitive", "trend"],
        invalid_contexts=["shock", "dislocation", "funding_missing"],
        preferred_stop_families=["funding_flip", "event_cut"],
        exit_families=["funding_harvest", "basis_funding_unwind", "scale_out", "time_stop"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=10.0,
            max_execution_cost_bps=18.0,
            min_depth_to_bar_volume_ratio=0.2,
            min_data_completeness_0_1=0.8,
            require_orderbook_context=True,
        ),
        preferred_timeframes=["5m", "15m", "1H", "4H"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="carry_vs_directional_trend_futures",
                comparison_class="same_futures_product_same_timeframe_bucket",
                evaluation_focus=["funding_drag", "expected_return_bps", "profit_factor"],
                minimum_samples=30,
                notes="Bewertet, ob Funding-/Basis-Playbooks echten Zusatznutzen liefern.",
            )
        ],
        anti_patterns=["carry_without_edge", "funding_event_too_far"],
        blacklist_criteria=["missing_futures_context", "feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["trend_continuation_core", "time_window_repricing"],
    ),
    PlaybookDefinition(
        playbook_id="news_shock_response",
        playbook_family="news_shock",
        title="News-Shock",
        summary="Eventgetriebene Reaktion auf News-/Schock-Regime mit explizitem Event-Exit und harter Risiko-Disziplin.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["news_driven", "shock"],
        invalid_contexts=["news_context_missing"],
        preferred_stop_families=["event_cut", "volatility_budget"],
        exit_families=["news_risk_flatten", "event_exit", "time_stop", "scale_out"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=25.0,
            max_execution_cost_bps=35.0,
            min_depth_to_bar_volume_ratio=0.1,
            min_data_completeness_0_1=0.78,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="news_shock_vs_no_trade_event",
                comparison_class="same_regime_same_market_family",
                evaluation_focus=["expected_return_bps", "time_to_stop_ms", "slippage_bps_entry"],
                minimum_samples=25,
                notes="Event-Playbooks muessen gegen No-Trade-Baseline ueberzeugend sein.",
            )
        ],
        anti_patterns=["shock_without_news_support", "event_too_old"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["session_open_drive", "time_window_repricing"],
    ),
    PlaybookDefinition(
        playbook_id="session_open_drive",
        playbook_family="session_open",
        title="Session Open",
        summary="Open-Drive oder Opening-Reversal in definierten Liquiditaetsfenstern mit enger Ausfuehrungskontrolle.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["session_transition", "expansion", "trend"],
        invalid_contexts=["session_window_absent", "shock"],
        preferred_stop_families=["session_open_fail", "microstructure_invalidation"],
        exit_families=["scale_out", "session_close", "liquidity_target"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=16.0,
            max_execution_cost_bps=24.0,
            min_depth_to_bar_volume_ratio=0.2,
            min_data_completeness_0_1=0.78,
        ),
        preferred_timeframes=["1m", "5m", "15m"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="session_open_vs_intraday_generic",
                comparison_class="same_market_family_same_timeframe_same_signal_class",
                evaluation_focus=["expected_return_bps", "time_to_tp1_ms", "profit_factor"],
                minimum_samples=30,
                notes="Open-Drive soll sich von generischen Intraday-Setups unterscheiden lassen.",
            )
        ],
        anti_patterns=["session_open_without_liquidity", "open_drive_after_delay"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["breakout_expansion", "time_window_repricing"],
        preferred_strategy_name="TrendContinuationStrategy",
    ),
    PlaybookDefinition(
        playbook_id="time_window_repricing",
        playbook_family="time_window_effect",
        title="Time-Window-Effekt",
        summary="Repricing um Funding-, Roll-, Hourly- oder definierte Zeitfenster mit explizitem Zeit-Exit.",
        target_market_families=["spot", "margin", "futures"],
        regime_suitability=["session_transition", "funding_skewed", "delivery_sensitive", "compression"],
        invalid_contexts=["time_window_absent", "shock_without_event"],
        preferred_stop_families=["time_window_expiry", "event_cut"],
        exit_families=["time_stop", "event_exit", "scale_out"],
        minimum_liquidity=PlaybookLiquidityConstraints(
            max_spread_bps=18.0,
            max_execution_cost_bps=26.0,
            min_depth_to_bar_volume_ratio=0.16,
            min_data_completeness_0_1=0.75,
        ),
        preferred_timeframes=["1m", "5m", "15m", "1H"],
        benchmark_rules=[
            PlaybookBenchmarkRule(
                benchmark_id="time_window_vs_session_open_same_window",
                comparison_class="same_market_family_same_window_bucket",
                evaluation_focus=["expected_return_bps", "time_to_stop_ms", "profit_factor"],
                minimum_samples=30,
                notes="Zeitfenster-Edges sollen gegen Session-Open-Edges differenziert messbar sein.",
            )
        ],
        anti_patterns=["window_absent", "event_distance_missing"],
        blacklist_criteria=["feature_quality_degraded", "liquidity_below_hard_floor"],
        counterfactual_candidates=["session_open_drive", "carry_funding_capture"],
        preferred_strategy_name="TrendContinuationStrategy",
    ),
)

PLAYBOOK_ID_SET = frozenset(item.playbook_id for item in PLAYBOOK_REGISTRY)
PLAYBOOK_FAMILY_SET = frozenset(item.playbook_family for item in PLAYBOOK_REGISTRY)
PLAYBOOK_REGISTRY_HASH = _stable_hash(
    {
        "registry_version": PLAYBOOK_REGISTRY_VERSION,
        "playbooks": [item.model_dump(mode="json") for item in PLAYBOOK_REGISTRY],
    }
)
_PLAYBOOKS_BY_ID = {item.playbook_id: item for item in PLAYBOOK_REGISTRY}
_DEFAULT_STRATEGY_BY_FAMILY = {
    item.playbook_family: item.preferred_strategy_name
    for item in PLAYBOOK_REGISTRY
    if item.preferred_strategy_name
}


def get_playbook(playbook_id: str | None) -> PlaybookDefinition | None:
    if not playbook_id:
        return None
    return _PLAYBOOKS_BY_ID.get(str(playbook_id).strip())


def preferred_strategy_for_playbook(playbook_id: str | None) -> str | None:
    playbook = get_playbook(playbook_id)
    return playbook.preferred_strategy_name if playbook is not None else None


def preferred_strategy_for_playbook_family(playbook_family: str | None) -> str | None:
    if not playbook_family:
        return None
    return _DEFAULT_STRATEGY_BY_FAMILY.get(str(playbook_family).strip())


def playbook_registry_descriptor() -> dict[str, object]:
    return {
        "registry_version": PLAYBOOK_REGISTRY_VERSION,
        "registry_hash": PLAYBOOK_REGISTRY_HASH,
        "playbook_count": len(PLAYBOOK_REGISTRY),
        "families": sorted(PLAYBOOK_FAMILY_SET),
        "playbooks": [
            {
                "playbook_id": item.playbook_id,
                "playbook_family": item.playbook_family,
                "title": item.title,
                "target_market_families": list(item.target_market_families),
                "regime_suitability": list(item.regime_suitability),
                "preferred_timeframes": list(item.preferred_timeframes),
                "benchmark_rule_ids": [rule.benchmark_id for rule in item.benchmark_rules],
                "preferred_strategy_name": item.preferred_strategy_name,
            }
            for item in PLAYBOOK_REGISTRY
        ],
    }
