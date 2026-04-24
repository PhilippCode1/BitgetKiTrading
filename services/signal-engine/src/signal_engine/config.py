"""
Zentrale, validierte Konfiguration der Signal-Engine.
Alle Gewichte muessen sich zu 1.0 summieren.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, TriggerType
from shared_py.bitget.instruments import (
    BitgetInstrumentIdentity,
    MarginAccountMode,
    MarketFamily,
)
from shared_py.eventbus import STREAM_DRAWING_UPDATED
from shared_py.model_contracts import MODEL_TIMEFRAMES, normalize_model_timeframe

TIMEFRAMES_ORDER = MODEL_TIMEFRAMES

# Dokumentierte MTF-Gewichte (Summe = 1.0) fuer Alignment-Berechnung
DEFAULT_MTF_TF_WEIGHTS: dict[str, float] = {
    "1m": 0.08,
    "5m": 0.12,
    "15m": 0.20,
    "1H": 0.30,
    "4H": 0.30,
}


class SignalEngineSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        populate_by_name=True,
    )
    production_required_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_fields + ("database_url", "redis_url")
    )
    production_required_non_local_fields: ClassVar[tuple[str, ...]] = (
        BaseServiceSettings.production_required_non_local_fields
        + ("database_url", "redis_url")
    )

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    signal_engine_port: int = Field(default=8050, alias="SIGNAL_ENGINE_PORT")
    bitget_market_family: MarketFamily | None = Field(
        default=None,
        alias="BITGET_MARKET_FAMILY",
    )
    bitget_product_type: str = Field(default="", alias="BITGET_PRODUCT_TYPE")
    bitget_margin_account_mode: MarginAccountMode | None = Field(
        default=None,
        alias="BITGET_MARGIN_ACCOUNT_MODE",
    )
    bitget_margin_coin: str | None = Field(default=None, alias="BITGET_MARGIN_COIN")
    risk_margin_mmr_halt_threshold_0_1: float = Field(
        default=0.20,
        alias="RISK_MARGIN_MMR_HALT_THRESHOLD_0_1",
        description="Margin: maintenance_margin_rate_0_1 aus Metadaten; darueber kein Sign-Off.",
    )
    risk_spot_balance_check_enabled: bool = Field(
        default=True,
        alias="RISK_SPOT_BALANCE_CHECK_ENABLED",
    )

    signal_stream: str = Field(default=STREAM_DRAWING_UPDATED, alias="SIGNAL_STREAM")
    signal_group: str = Field(default="signal-engine", alias="SIGNAL_GROUP")
    signal_consumer: str = Field(default="se-1", alias="SIGNAL_CONSUMER")
    signal_stable_replay_signal_ids: bool = Field(
        default=True,
        alias="SIGNAL_STABLE_REPLAY_SIGNAL_IDS",
        description="Bei Replay-Trace: deterministische signal_id aus Session+upstream event",
    )

    signal_min_score_for_micro: float = Field(default=35.0, alias="SIGNAL_MIN_SCORE_FOR_MICRO")
    signal_min_score_for_core: float = Field(default=55.0, alias="SIGNAL_MIN_SCORE_FOR_CORE")
    signal_min_score_for_gross: float = Field(default=72.0, alias="SIGNAL_MIN_SCORE_FOR_GROSS")
    signal_rejection_enabled: bool = Field(default=True, alias="SIGNAL_REJECTION_ENABLED")

    signal_weight_structure: float = Field(default=0.22, alias="SIGNAL_WEIGHT_STRUCTURE")
    signal_weight_momentum: float = Field(default=0.20, alias="SIGNAL_WEIGHT_MOMENTUM")
    signal_weight_multi_timeframe: float = Field(default=0.22, alias="SIGNAL_WEIGHT_MULTI_TIMEFRAME")
    signal_weight_news: float = Field(default=0.10, alias="SIGNAL_WEIGHT_NEWS")
    signal_weight_risk: float = Field(default=0.18, alias="SIGNAL_WEIGHT_RISK")
    signal_weight_history: float = Field(default=0.08, alias="SIGNAL_WEIGHT_HISTORY")
    signal_news_in_composite_enabled: bool = Field(
        default=True,
        alias="SIGNAL_NEWS_IN_COMPOSITE_ENABLED",
    )
    signal_news_shock_rejection_enabled: bool = Field(
        default=True,
        alias="SIGNAL_NEWS_SHOCK_REJECTION_ENABLED",
    )
    structured_market_context_enabled: bool = Field(
        default=True,
        alias="STRUCTURED_MARKET_CONTEXT_ENABLED",
        description="Deterministischer Kontextlayer (News/Makro/Listing/...) siehe docs/structured_market_context.md",
    )
    smc_news_decay_half_life_minutes: float = Field(
        default=120.0,
        alias="SMC_NEWS_DECAY_HALF_LIFE_MINUTES",
    )
    smc_surprise_directional_threshold_0_1: float = Field(
        default=0.58,
        alias="SMC_SURPRISE_DIRECTIONAL_THRESHOLD_0_1",
    )
    smc_surprise_live_throttle_threshold_0_1: float = Field(
        default=0.52,
        alias="SMC_SURPRISE_LIVE_THROTTLE_THRESHOLD_0_1",
    )
    smc_composite_shrink_min_0_1: float = Field(
        default=0.88,
        alias="SMC_COMPOSITE_SHRINK_MIN_0_1",
    )
    smc_enable_structural_break_boost: bool = Field(
        default=True,
        alias="SMC_ENABLE_STRUCTURAL_BREAK_BOOST",
    )
    smc_hard_event_veto_enabled: bool = Field(
        default=False,
        alias="SMC_HARD_EVENT_VETO_ENABLED",
        description="Optional: harte No-Trade-Codes context_hard_event_veto_* bei extremem Surprise.",
    )
    smc_hard_event_veto_surprise_0_1: float = Field(
        default=0.82,
        alias="SMC_HARD_EVENT_VETO_SURPRISE_0_1",
    )
    smc_playbook_news_sensitive_surprise_mult: float = Field(
        default=1.1,
        alias="SMC_PLAYBOOK_NEWS_SENSITIVE_SURPRISE_MULT",
    )
    smc_playbook_trend_surprise_mult: float = Field(
        default=0.96,
        alias="SMC_PLAYBOOK_TREND_SURPRISE_MULT",
    )

    signal_max_data_age_ms: int = Field(default=300_000, alias="SIGNAL_MAX_DATA_AGE_MS")
    signal_max_structure_age_ms: int = Field(default=300_000, alias="SIGNAL_MAX_STRUCTURE_AGE_MS")
    signal_max_drawing_age_ms: int = Field(default=300_000, alias="SIGNAL_MAX_DRAWING_AGE_MS")
    signal_max_news_age_ms: int = Field(default=3_600_000, alias="SIGNAL_MAX_NEWS_AGE_MS")
    signal_max_orderbook_age_ms: int = Field(default=20_000, alias="SIGNAL_MAX_ORDERBOOK_AGE_MS")
    signal_max_funding_feature_age_ms: int = Field(
        default=900_000,
        alias="SIGNAL_MAX_FUNDING_FEATURE_AGE_MS",
    )
    signal_max_open_interest_age_ms: int = Field(
        default=300_000,
        alias="SIGNAL_MAX_OPEN_INTEREST_AGE_MS",
    )
    signal_max_spread_bps: float = Field(default=8.0, alias="SIGNAL_MAX_SPREAD_BPS")
    signal_max_execution_cost_bps: float = Field(
        default=18.0,
        alias="SIGNAL_MAX_EXECUTION_COST_BPS",
    )
    signal_max_adverse_funding_bps: float = Field(
        default=5.0,
        alias="SIGNAL_MAX_ADVERSE_FUNDING_BPS",
    )
    signal_default_news_neutral_score: float = Field(
        default=50.0, alias="SIGNAL_DEFAULT_NEWS_NEUTRAL_SCORE"
    )
    signal_default_history_neutral_score: float = Field(
        default=50.0, alias="SIGNAL_DEFAULT_HISTORY_NEUTRAL_SCORE"
    )
    signal_min_reward_risk: float = Field(default=1.2, alias="SIGNAL_MIN_REWARD_RISK")
    signal_min_risk_score: float = Field(default=35.0, alias="SIGNAL_MIN_RISK_SCORE")
    signal_min_structure_score_for_directional: float = Field(
        default=42.0, alias="SIGNAL_MIN_STRUCTURE_SCORE_FOR_DIRECTIONAL"
    )
    signal_min_multi_tf_score_for_directional: float = Field(
        default=38.0, alias="SIGNAL_MIN_MULTI_TF_SCORE_FOR_DIRECTIONAL"
    )
    signal_scoring_model_version: str = Field(
        default="v1.0.0", alias="SIGNAL_SCORING_MODEL_VERSION"
    )
    take_trade_model_refresh_ms: int = Field(
        default=60_000,
        alias="TAKE_TRADE_MODEL_REFRESH_MS",
    )
    model_registry_v2_enabled: bool = Field(default=False, alias="MODEL_REGISTRY_V2_ENABLED")
    model_calibration_required: bool = Field(default=False, alias="MODEL_CALIBRATION_REQUIRED")
    model_champion_name: str = Field(default="take_trade_prob", alias="MODEL_CHAMPION_NAME")
    model_registry_scoped_slots_enabled: bool = Field(
        default=False,
        alias="MODEL_REGISTRY_SCOPED_SLOTS_ENABLED",
        description="Wenn true und Registry V2: Champion-Aufloesung router_slot > playbook > regime > family > global.",
    )
    model_max_uncertainty: float = Field(
        default=0.63,
        alias="MODEL_MAX_UNCERTAINTY",
        description="Harte Abstinenz: compositer Uncertainty-Score darueber -> do_not_trade",
    )
    model_uncertainty_shadow_lane: float = Field(
        default=0.48,
        alias="MODEL_UNCERTAINTY_SHADOW_LANE",
    )
    model_uncertainty_paper_lane: float = Field(
        default=0.36,
        alias="MODEL_UNCERTAINTY_PAPER_LANE",
    )
    model_ood_hard_abstain_score: float = Field(
        default=0.88,
        alias="MODEL_OOD_HARD_ABSTAIN_SCORE",
    )
    model_ood_shadow_lane_score: float = Field(
        default=0.58,
        alias="MODEL_OOD_SHADOW_LANE_SCORE",
    )
    model_ood_paper_lane_score: float = Field(
        default=0.42,
        alias="MODEL_OOD_PAPER_LANE_SCORE",
    )
    model_shadow_divergence_hard_abstain: float = Field(
        default=0.42,
        alias="MODEL_SHADOW_DIVERGENCE_HARD_ABSTAIN",
    )
    model_shadow_divergence_shadow_lane: float = Field(
        default=0.26,
        alias="MODEL_SHADOW_DIVERGENCE_SHADOW_LANE",
    )
    model_ood_robust_z_threshold: float = Field(
        default=6.0,
        alias="MODEL_OOD_ROBUST_Z_THRESHOLD",
    )
    model_ood_max_flagged_features: int = Field(
        default=2,
        alias="MODEL_OOD_MAX_FLAGGED_FEATURES",
    )
    model_shadow_divergence_threshold: float = Field(
        default=0.30,
        alias="MODEL_SHADOW_DIVERGENCE_THRESHOLD",
    )
    mdk_specialist_dissent_abstain_0_1: float = Field(
        default=0.72,
        alias="MDK_SPECIALIST_DISSENT_ABSTAIN_0_1",
        description="Meta-Decision-Kernel: Dissent-Score ab hier -> harte Abstinenz.",
    )
    mdk_stop_executability_min_0_1: float = Field(
        default=0.30,
        alias="MDK_STOP_EXECUTABLE_MIN_0_1",
        description="Stop-Ausfuehrbarkeit (0..1) darunter -> Kernel-Abstinenz, falls gesetzt.",
    )
    mdk_min_expected_utility_proxy_0_1: float = Field(
        default=0.08,
        alias="MDK_MIN_EXPECTED_UTILITY_PROXY_0_1",
        description="Erwartungsnutzen-Proxy (kalibrierte Komponenten) darunter -> Abstinenz.",
    )
    hybrid_decision_min_take_trade_prob: float = Field(
        default=0.58,
        alias="HYBRID_DECISION_MIN_TAKE_TRADE_PROB",
    )
    hybrid_decision_min_expected_return_bps: float = Field(
        default=6.0,
        alias="HYBRID_DECISION_MIN_EXPECTED_RETURN_BPS",
    )
    hybrid_decision_max_expected_mae_bps: float = Field(
        default=90.0,
        alias="HYBRID_DECISION_MAX_EXPECTED_MAE_BPS",
    )
    hybrid_decision_min_projected_rr: float = Field(
        default=1.20,
        alias="HYBRID_DECISION_MIN_PROJECTED_RR",
    )
    hybrid_decision_regime_conflict_threshold: float = Field(
        default=0.70,
        alias="HYBRID_DECISION_REGIME_CONFLICT_THRESHOLD",
    )
    hybrid_decision_strong_confidence: float = Field(
        default=0.80,
        alias="HYBRID_DECISION_STRONG_CONFIDENCE",
    )
    meta_prob_ood_shrink_factor: float = Field(
        default=0.72,
        alias="META_PROB_OOD_SHRINK_FACTOR",
    )
    meta_prob_uncertainty_shrink_weight: float = Field(
        default=0.35,
        alias="META_PROB_UNCERTAINTY_SHRINK_WEIGHT",
    )
    meta_lane_paper_prob_margin: float = Field(
        default=0.04,
        alias="META_LANE_PAPER_PROB_MARGIN",
    )
    meta_lane_paper_uncertainty_at_least: float = Field(
        default=0.42,
        alias="META_LANE_PAPER_UNCERTAINTY_AT_LEAST",
    )
    meta_lane_paper_execution_cost_bps_at_least: float = Field(
        default=15.0,
        alias="META_LANE_PAPER_EXECUTION_COST_BPS_AT_LEAST",
    )
    meta_lane_paper_risk_score_below: float = Field(
        default=45.0,
        alias="META_LANE_PAPER_RISK_SCORE_BELOW",
    )
    meta_lane_paper_history_score_below: float = Field(
        default=42.0,
        alias="META_LANE_PAPER_HISTORY_SCORE_BELOW",
    )
    meta_lane_paper_structure_score_below: float = Field(
        default=44.0,
        alias="META_LANE_PAPER_STRUCTURE_SCORE_BELOW",
    )
    leverage_signal_max_volatility_band: float = Field(
        default=0.35,
        alias="LEVERAGE_SIGNAL_MAX_VOLATILITY_BAND",
    )
    leverage_signal_min_depth_ratio: float = Field(
        default=0.60,
        alias="LEVERAGE_SIGNAL_MIN_DEPTH_RATIO",
    )
    leverage_signal_max_impact_bps_10000: float = Field(
        default=10.0,
        alias="LEVERAGE_SIGNAL_MAX_IMPACT_BPS_10000",
    )

    signal_explain_version: str = Field(default="1.0", alias="SIGNAL_EXPLAIN_VERSION")
    stop_min_atr_mult: float = Field(default=0.6, alias="STOP_MIN_ATR_MULT")
    signal_default_stop_trigger_type: TriggerType = Field(
        default="mark_price", alias="SIGNAL_DEFAULT_STOP_TRIGGER_TYPE"
    )
    stop_budget_policy_enabled: bool = Field(default=True, alias="STOP_BUDGET_POLICY_ENABLED")
    stop_budget_anchor_leverage: int = Field(default=7, alias="STOP_BUDGET_ANCHOR_LEVERAGE")
    stop_budget_max_pct_at_anchor: float = Field(default=0.01, alias="STOP_BUDGET_MAX_PCT_AT_ANCHOR")
    stop_budget_high_leverage_floor: int = Field(default=50, alias="STOP_BUDGET_HIGH_LEVERAGE_FLOOR")
    stop_budget_floor_pct: float = Field(default=0.001, alias="STOP_BUDGET_FLOOR_PCT")
    stop_budget_tick_steps_min: int = Field(default=2, alias="STOP_BUDGET_TICK_STEPS_MIN")
    stop_budget_spread_floor_mult: float = Field(default=2.5, alias="STOP_BUDGET_SPREAD_FLOOR_MULT")
    stop_budget_atr_floor_mult: float = Field(default=0.12, alias="STOP_BUDGET_ATR_FLOOR_MULT")
    stop_budget_impact_floor_mult: float = Field(default=0.35, alias="STOP_BUDGET_IMPACT_FLOOR_MULT")
    stop_budget_slippage_floor_mult: float = Field(default=0.55, alias="STOP_BUDGET_SLIPPAGE_FLOOR_MULT")
    stop_budget_mae_structure_mult: float = Field(default=0.55, alias="STOP_BUDGET_MAE_STRUCTURE_MULT")
    stop_budget_family_spot_floor_scale: float = Field(default=1.0, alias="STOP_BUDGET_FAMILY_SPOT_FLOOR_SCALE")
    stop_budget_family_margin_floor_scale: float = Field(default=1.04, alias="STOP_BUDGET_FAMILY_MARGIN_FLOOR_SCALE")
    stop_budget_family_futures_floor_scale: float = Field(default=1.08, alias="STOP_BUDGET_FAMILY_FUTURES_FLOOR_SCALE")
    stop_budget_regime_stress_floor_scale: float = Field(default=1.22, alias="STOP_BUDGET_REGIME_STRESS_FLOOR_SCALE")
    stop_budget_regime_chop_floor_scale: float = Field(default=1.10, alias="STOP_BUDGET_REGIME_CHOP_FLOOR_SCALE")
    stop_budget_min_executable_floor_pct: float = Field(
        default=0.00005,
        alias="STOP_BUDGET_MIN_EXECUTABLE_FLOOR_PCT",
        description="Absolutes Mindest-% fuer Ausfuehrbarkeit (Fallback ohne Tick)",
    )
    stop_budget_hard_fragility_abstain: bool = Field(default=True, alias="STOP_BUDGET_HARD_FRAGILITY_ABSTAIN")
    stop_budget_liquidation_stress_block: float = Field(
        default=0.82,
        alias="STOP_BUDGET_LIQUIDATION_STRESS_BLOCK",
        description="Bei Stress >= Schwelle und extrem engem Stop: harte Sperre (0=aus)",
    )
    stop_budget_liquidation_tight_stop_max_pct: float = Field(
        default=0.0035,
        alias="STOP_BUDGET_LIQUIDATION_TIGHT_STOP_MAX_PCT",
        description="Stop gilt als 'extrem eng' unterhalb dieses %-Abstands bei hohem Liq-Stress",
    )

    eventbus_default_block_ms: int = Field(default=2000, alias="EVENTBUS_DEFAULT_BLOCK_MS")
    eventbus_default_count: int = Field(default=50, alias="EVENTBUS_DEFAULT_COUNT")
    eventbus_dedupe_ttl_sec: int = Field(default=86400, alias="EVENTBUS_DEDUPE_TTL_SEC")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    signal_operator_intel_outbox_enabled: bool = Field(
        default=False,
        alias="SIGNAL_OPERATOR_INTEL_OUTBOX_ENABLED",
        description=(
            "Publiziert operator_intel nach jedem persistierten Signal (events:operator_intel -> alert-engine). "
            "Nur Informationskanal; keine Strategie-Mutation."
        ),
    )

    @field_validator("signal_stream")
    @classmethod
    def _signal_stream(cls, v: str) -> str:
        n = v.strip()
        if n != STREAM_DRAWING_UPDATED:
            raise ValueError(
                "SIGNAL_STREAM muss fuer Prompt 13 events:drawing_updated sein"
            )
        return n

    @field_validator("signal_default_stop_trigger_type")
    @classmethod
    def _stop_trigger(cls, v: str) -> str:
        n = v.strip().lower()
        if n not in ("mark_price", "fill_price"):
            raise ValueError(
                "SIGNAL_DEFAULT_STOP_TRIGGER_TYPE muss mark_price oder fill_price sein"
            )
        return n

    @field_validator(
        "signal_max_data_age_ms",
        "signal_max_structure_age_ms",
        "signal_max_drawing_age_ms",
        "signal_max_news_age_ms",
        "signal_max_orderbook_age_ms",
        "signal_max_funding_feature_age_ms",
        "signal_max_open_interest_age_ms",
        "take_trade_model_refresh_ms",
    )
    @classmethod
    def _positive_age(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("SIGNAL_MAX_*_AGE_MS und TAKE_TRADE_MODEL_REFRESH_MS muessen > 0 sein")
        return v

    @field_validator(
        "signal_max_spread_bps",
        "signal_max_execution_cost_bps",
        "signal_max_adverse_funding_bps",
        "model_ood_robust_z_threshold",
        "hybrid_decision_min_expected_return_bps",
        "hybrid_decision_max_expected_mae_bps",
        "hybrid_decision_min_projected_rr",
        "leverage_signal_max_volatility_band",
        "leverage_signal_max_impact_bps_10000",
        "stop_budget_max_pct_at_anchor",
        "stop_budget_floor_pct",
        "stop_budget_spread_floor_mult",
        "stop_budget_atr_floor_mult",
        "stop_budget_impact_floor_mult",
        "stop_budget_slippage_floor_mult",
        "stop_budget_mae_structure_mult",
        "stop_budget_family_spot_floor_scale",
        "stop_budget_family_margin_floor_scale",
        "stop_budget_family_futures_floor_scale",
        "stop_budget_regime_stress_floor_scale",
        "stop_budget_regime_chop_floor_scale",
        "stop_budget_min_executable_floor_pct",
        "stop_budget_liquidation_stress_block",
        "stop_budget_liquidation_tight_stop_max_pct",
    )
    @classmethod
    def _non_negative_threshold(cls, v: float) -> float:
        if v < 0:
            raise ValueError(
                "SIGNAL_MAX_*, MODEL_OOD_* und HYBRID_DECISION_*_BPS/RR duerfen nicht negativ sein"
            )
        return v

    @field_validator(
        "model_max_uncertainty",
        "model_uncertainty_shadow_lane",
        "model_uncertainty_paper_lane",
        "model_ood_hard_abstain_score",
        "model_ood_shadow_lane_score",
        "model_ood_paper_lane_score",
        "model_shadow_divergence_hard_abstain",
        "model_shadow_divergence_shadow_lane",
        "model_shadow_divergence_threshold",
        "mdk_specialist_dissent_abstain_0_1",
        "mdk_stop_executability_min_0_1",
        "mdk_min_expected_utility_proxy_0_1",
        "hybrid_decision_min_take_trade_prob",
        "hybrid_decision_regime_conflict_threshold",
        "hybrid_decision_strong_confidence",
        "leverage_signal_min_depth_ratio",
        "meta_prob_ood_shrink_factor",
        "meta_prob_uncertainty_shrink_weight",
        "meta_lane_paper_prob_margin",
        "meta_lane_paper_uncertainty_at_least",
        "smc_surprise_directional_threshold_0_1",
        "smc_surprise_live_throttle_threshold_0_1",
        "smc_composite_shrink_min_0_1",
        "smc_hard_event_veto_surprise_0_1",
    )
    @classmethod
    def _unit_interval_threshold(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError(
                "MODEL_MAX_UNCERTAINTY, MODEL_SHADOW_DIVERGENCE_THRESHOLD, HYBRID_DECISION_* "
                "und META_*_SHRINK/_MARGIN/_UNCERTAINTY muessen 0..1 sein"
            )
        return v

    @field_validator("smc_news_decay_half_life_minutes")
    @classmethod
    def _smc_half_life(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("SMC_NEWS_DECAY_HALF_LIFE_MINUTES muss > 0 sein")
        return v

    @field_validator(
        "smc_playbook_news_sensitive_surprise_mult",
        "smc_playbook_trend_surprise_mult",
    )
    @classmethod
    def _smc_playbook_mult(cls, v: float) -> float:
        if v <= 0 or v > 1.5:
            raise ValueError("SMC_PLAYBOOK_*_MULT muss in (0, 1.5] liegen")
        return v

    @field_validator(
        "meta_lane_paper_execution_cost_bps_at_least",
        "meta_lane_paper_risk_score_below",
        "meta_lane_paper_history_score_below",
        "meta_lane_paper_structure_score_below",
    )
    @classmethod
    def _meta_lane_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("META_LANE_PAPER_* Schwellen duerfen nicht negativ sein")
        return v

    @field_validator("model_ood_max_flagged_features")
    @classmethod
    def _positive_ood_count(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("MODEL_OOD_MAX_FLAGGED_FEATURES muss > 0 sein")
        return v

    @field_validator("model_ood_robust_z_threshold")
    @classmethod
    def _positive_ood_distance(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("MODEL_OOD_ROBUST_Z_THRESHOLD muss > 0 sein")
        return v

    @field_validator("stop_min_atr_mult")
    @classmethod
    def _stop_atr_mult(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("STOP_MIN_ATR_MULT muss > 0 sein")
        return v

    @field_validator("bitget_market_family", mode="before")
    @classmethod
    def _market_family(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("bitget_product_type", mode="before")
    @classmethod
    def _product_type(cls, value: str | None) -> str:
        if value is None:
            return ""
        return value.strip().upper()

    @field_validator("bitget_margin_account_mode", mode="before")
    @classmethod
    def _margin_mode(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        return normalized or None

    @field_validator("bitget_margin_coin", mode="before")
    @classmethod
    def _margin_coin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("signal_engine_port")
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("SIGNAL_ENGINE_PORT ungueltig")
        return v

    @field_validator(
        "signal_weight_structure",
        "signal_weight_momentum",
        "signal_weight_multi_timeframe",
        "signal_weight_risk",
        "signal_weight_history",
    )
    @classmethod
    def _nonneg_weight(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Gewichte duerfen nicht negativ sein")
        return v

    @field_validator("signal_weight_news")
    @classmethod
    def _nonneg_news_weight_with_cap(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Gewichte duerfen nicht negativ sein")
        if v > 0.15:
            raise ValueError(
                "SIGNAL_WEIGHT_NEWS darf maximal 0.15 sein (News bleibt begrenztes Zusatzsignal)"
            )
        return v

    @model_validator(mode="after")
    def _weights_sum_one(self) -> "SignalEngineSettings":
        if self.bitget_market_family is None:
            families = self.bitget_universe_market_families_list()
            object.__setattr__(self, "bitget_market_family", families[0] if families else "spot")
        if self.bitget_market_family == "futures" and not self.bitget_product_type:
            object.__setattr__(
                self,
                "bitget_product_type",
                self.default_futures_product_type(),
            )
        if self.bitget_market_family == "spot":
            object.__setattr__(self, "bitget_margin_account_mode", "cash")
        elif self.bitget_margin_account_mode is None:
            object.__setattr__(
                self,
                "bitget_margin_account_mode",
                "isolated" if self.bitget_market_family == "futures" else self.bitget_margin_default_account_mode,
            )
        s = (
            self.signal_weight_structure
            + self.signal_weight_momentum
            + self.signal_weight_multi_timeframe
            + self.signal_weight_news
            + self.signal_weight_risk
            + self.signal_weight_history
        )
        if abs(s - 1.0) > 0.0001:
            raise ValueError(
                f"Summe der SIGNAL_WEIGHT_* muss 1.0 sein, ist {s:.6f}"
            )
        return self

    @model_validator(mode="after")
    def _uncertainty_gate_ordering(self) -> "SignalEngineSettings":
        if not (
            self.model_uncertainty_paper_lane
            <= self.model_uncertainty_shadow_lane
            <= self.model_max_uncertainty
        ):
            raise ValueError(
                "MODEL_UNCERTAINTY_PAPER_LANE <= MODEL_UNCERTAINTY_SHADOW_LANE <= MODEL_MAX_UNCERTAINTY"
            )
        if not (
            self.model_ood_paper_lane_score
            <= self.model_ood_shadow_lane_score
            <= self.model_ood_hard_abstain_score
        ):
            raise ValueError(
                "MODEL_OOD_PAPER_LANE_SCORE <= MODEL_OOD_SHADOW_LANE_SCORE <= MODEL_OOD_HARD_ABSTAIN_SCORE"
            )
        if self.model_shadow_divergence_shadow_lane > self.model_shadow_divergence_hard_abstain:
            raise ValueError(
                "MODEL_SHADOW_DIVERGENCE_SHADOW_LANE darf nicht groesser sein als HARD_ABSTAIN"
            )
        return self

    @model_validator(mode="after")
    def _stop_budget_curve_valid(self) -> "SignalEngineSettings":
        if self.stop_budget_anchor_leverage < 1:
            raise ValueError("STOP_BUDGET_ANCHOR_LEVERAGE muss >= 1 sein")
        if self.stop_budget_high_leverage_floor <= self.stop_budget_anchor_leverage:
            raise ValueError("STOP_BUDGET_HIGH_LEVERAGE_FLOOR muss > STOP_BUDGET_ANCHOR_LEVERAGE sein")
        if not 0 < self.stop_budget_floor_pct < self.stop_budget_max_pct_at_anchor <= 0.2:
            raise ValueError(
                "STOP_BUDGET_FLOOR_PCT < STOP_BUDGET_MAX_PCT_AT_ANCHOR <= 0.2 und > 0 erforderlich"
            )
        if self.stop_budget_tick_steps_min < 1:
            raise ValueError("STOP_BUDGET_TICK_STEPS_MIN muss >= 1 sein")
        if self.stop_budget_min_executable_floor_pct < 0:
            raise ValueError("STOP_BUDGET_MIN_EXECUTABLE_FLOOR_PCT darf nicht negativ sein")
        return self

    def weight_tuple(self) -> tuple[float, float, float, float, float, float]:
        if self.signal_news_in_composite_enabled:
            return (
                self.signal_weight_structure,
                self.signal_weight_momentum,
                self.signal_weight_multi_timeframe,
                self.signal_weight_news,
                self.signal_weight_risk,
                self.signal_weight_history,
            )
        extra = self.signal_weight_news
        return (
            self.signal_weight_structure + extra,
            self.signal_weight_momentum,
            self.signal_weight_multi_timeframe,
            0.0,
            self.signal_weight_risk,
            self.signal_weight_history,
        )

    def instrument_identity(self, *, symbol: str) -> BitgetInstrumentIdentity:
        return BitgetInstrumentIdentity(
            market_family=self.bitget_market_family,
            symbol=symbol,
            product_type=self.bitget_product_type if self.bitget_market_family == "futures" else None,
            margin_coin=self.bitget_margin_coin,
            margin_account_mode=self.bitget_margin_account_mode,
            public_ws_inst_type=(
                self.bitget_product_type if self.bitget_market_family == "futures" else "SPOT"
            ),
            private_ws_inst_type=(
                self.bitget_product_type
                if self.bitget_market_family == "futures"
                else ("MARGIN" if self.bitget_market_family == "margin" else "SPOT")
            ),
            metadata_source="signal_engine.runtime_config",
            metadata_verified=False,
            supports_funding=self.bitget_market_family == "futures",
            supports_open_interest=self.bitget_market_family == "futures",
            supports_long_short=self.bitget_market_family in {"futures", "margin"},
            supports_shorting=self.bitget_market_family in {"futures", "margin"},
            supports_reduce_only=self.bitget_market_family == "futures",
            supports_leverage=self.bitget_market_family in {"futures", "margin"},
            uses_spot_public_market_data=self.bitget_market_family in {"spot", "margin"},
        )


def normalize_timeframe(tf: str) -> str:
    return normalize_model_timeframe(tf)
