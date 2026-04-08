from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict

from config.settings import BaseServiceSettings, StrategyExecutionMode, TriggerType
from shared_py.bitget.instruments import (
    BitgetInstrumentIdentity,
    MarginAccountMode,
    MarketFamily,
    endpoint_profile_for,
)


class PaperBrokerSettings(BaseServiceSettings):
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

    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")
    paper_broker_port: int = Field(default=8085, alias="PAPER_BROKER_PORT")
    paper_account_initial_equity_usdt: str = Field(default="10000", alias="PAPER_ACCOUNT_INITIAL_EQUITY_USDT")
    paper_default_margin_mode: str = Field(default="isolated", alias="PAPER_DEFAULT_MARGIN_MODE")
    paper_default_leverage: int = Field(default=7, alias="PAPER_DEFAULT_LEVERAGE")
    paper_max_leverage: int = Field(default=75, alias="PAPER_MAX_LEVERAGE")
    paper_default_slippage_bps: str = Field(default="3", alias="PAPER_DEFAULT_SLIPPAGE_BPS")
    paper_orderbook_levels: int = Field(default=25, alias="PAPER_ORDERBOOK_LEVELS")
    paper_fee_source: str = Field(default="contract_config", alias="PAPER_FEE_SOURCE")
    paper_default_maker_fee: str = Field(default="0.0002", alias="PAPER_DEFAULT_MAKER_FEE")
    paper_default_taker_fee: str = Field(default="0.0006", alias="PAPER_DEFAULT_TAKER_FEE")
    paper_funding_source: str = Field(default="events_or_rest", alias="PAPER_FUNDING_SOURCE")
    paper_mmr_base: str = Field(default="0.005", alias="PAPER_MMR_BASE")
    paper_liq_fee_buffer_usdt: str = Field(default="5", alias="PAPER_LIQ_FEE_BUFFER_USDT")
    leverage_stop_distance_scale_bps: float = Field(
        default=1500.0,
        alias="LEVERAGE_STOP_DISTANCE_SCALE_BPS",
        description="Paper: Hebel-Obergrenze vs. Stop-Distanz (bps); float, konsistent mit BaseServiceSettings-Validator.",
    )
    leverage_min_liquidation_buffer_bps: str = Field(
        default="35",
        alias="LEVERAGE_MIN_LIQUIDATION_BUFFER_BPS",
    )
    bitget_api_base_url: str = Field(default="https://api.bitget.com", alias="BITGET_API_BASE_URL")
    bitget_market_family: MarketFamily | None = Field(
        default=None,
        alias="BITGET_MARKET_FAMILY",
    )
    bitget_margin_account_mode: MarginAccountMode | None = Field(
        default=None,
        alias="BITGET_MARGIN_ACCOUNT_MODE",
    )
    bitget_product_type: str = Field(default="", alias="BITGET_PRODUCT_TYPE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    eventbus_dedupe_ttl_sec: int = Field(default=0, alias="EVENTBUS_DEDUPE_TTL_SEC")
    paper_default_symbol: str = Field(default="", alias="PAPER_DEFAULT_SYMBOL")
    paper_require_catalog_tradeable: bool = Field(
        default=False,
        alias="PAPER_REQUIRE_CATALOG_TRADEABLE",
        description="Vor Open: Bitget-Katalog muss trading_enabled liefern (Multi-Asset-Produktion).",
    )
    paper_stop_budget_sizing_enabled: bool = Field(
        default=True,
        alias="PAPER_STOP_BUDGET_SIZING_ENABLED",
        description="Positionsgroesse optional an Hebel-indexiertes Stop-Budget koppeln.",
    )
    paper_stop_budget_equity_risk_fraction: str = Field(
        default="0.005",
        alias="PAPER_STOP_BUDGET_EQUITY_RISK_FRACTION",
        description="Anteil Equity als Risiko-Proxy relativ zur Stop-Budget-Distanz (nicht Live-Pflicht).",
    )
    paper_stop_budget_qty_cap_mult: str = Field(
        default="2.5",
        alias="PAPER_STOP_BUDGET_QTY_CAP_MULT",
        description="Max-Faktor ueber signal_class-Basis-Qty bei Stop-Budget-Sizing.",
    )
    paper_worker_group: str = Field(default="paper-broker", alias="PAPER_WORKER_GROUP")
    paper_worker_consumer: str = Field(default="pb-1", alias="PAPER_WORKER_CONSUMER")

    paper_stop_tp_enabled: bool = Field(default=True, alias="PAPER_STOP_TP_ENABLED")
    stop_trigger_type_default: TriggerType = Field(
        default="mark_price",
        alias="STOP_TRIGGER_TYPE_DEFAULT",
    )
    tp_trigger_type_default: TriggerType = Field(
        default="fill_price",
        alias="TP_TRIGGER_TYPE_DEFAULT",
    )
    stop_pad_bps: str = Field(default="15", alias="STOP_PAD_BPS")
    stop_min_atr_mult: str = Field(default="0.6", alias="STOP_MIN_ATR_MULT")
    atr_mult_1m: str = Field(default="1.2", alias="ATR_MULT_1M")
    atr_mult_5m: str = Field(default="1.0", alias="ATR_MULT_5M")
    atr_mult_15m: str = Field(default="0.9", alias="ATR_MULT_15M")
    atr_mult_1h: str = Field(default="0.8", alias="ATR_MULT_1H")
    atr_mult_4h: str = Field(default="0.7", alias="ATR_MULT_4H")
    liq_stop_scan_bps: str = Field(default="25", alias="LIQ_STOP_SCAN_BPS")
    liq_stop_escape_bps: str = Field(default="10", alias="LIQ_STOP_ESCAPE_BPS")
    liq_stop_avoid_bps: str = Field(default="8", alias="LIQ_STOP_AVOID_BPS")
    tp1_pct: str = Field(default="0.30", alias="TP1_PCT")
    tp2_pct: str = Field(default="0.30", alias="TP2_PCT")
    tp3_pct: str = Field(default="0.40", alias="TP3_PCT")
    runner_trail_atr_mult: str = Field(default="1.0", alias="RUNNER_TRAIL_ATR_MULT")
    exit_break_even_after_tp_index: int = Field(
        default=0,
        alias="EXIT_BREAK_EVEN_AFTER_TP_INDEX",
    )
    exit_runner_enabled: bool = Field(default=True, alias="EXIT_RUNNER_ENABLED")
    min_rr_for_trade: str = Field(default="1.2", alias="MIN_RR_FOR_TRADE")
    default_atr_fallback_bps: str = Field(default="50", alias="DEFAULT_ATR_FALLBACK_BPS")

    strategy_exec_enabled: bool = Field(default=False, alias="STRATEGY_EXEC_ENABLED")
    strat_base_qty_btc: str = Field(default="0.02", alias="STRAT_BASE_QTY_BTC")
    micro_size_mult: str = Field(default="0.25", alias="MICRO_SIZE_MULT")
    gross_size_mult: str = Field(default="2.0", alias="GROSS_SIZE_MULT")
    news_shock_score: int = Field(default=80, alias="NEWS_SHOCK_SCORE")
    news_cooldown_sec: int = Field(default=1800, alias="NEWS_COOLDOWN_SEC")
    close_partial_on_news_shock_pct: str = Field(default="0.50", alias="CLOSE_PARTIAL_ON_NEWS_SHOCK_PCT")
    use_drawing_target_updates: bool = Field(default=True, alias="USE_DRAWING_TARGET_UPDATES")
    use_structure_flip_exit: bool = Field(default=True, alias="USE_STRUCTURE_FLIP_EXIT")
    structure_flip_full_close: bool = Field(default=False, alias="STRUCTURE_FLIP_FULL_CLOSE")
    structure_flip_tighten_bps: str = Field(default="25", alias="STRUCTURE_FLIP_TIGHTEN_BPS")
    strategy_default_account_id: str | None = Field(default=None, alias="PAPER_STRATEGY_ACCOUNT_ID")
    strategy_signal_queue_max: int = Field(default=50, alias="STRATEGY_SIGNAL_QUEUE_MAX")

    strategy_registry_enabled: bool = Field(default=False, alias="STRATEGY_REGISTRY_ENABLED")
    strategy_registry_event_stream: str = Field(
        default="events:strategy_registry_updated", alias="STRATEGY_REGISTRY_EVENT_STREAM"
    )

    billing_prepaid_gate_enabled: bool = Field(
        default=False,
        alias="BILLING_PREPAID_GATE_ENABLED",
        description="Neue Paper-Positionen nur bei ausreichendem app.customer_wallet (Tenant).",
    )
    billing_prepaid_tenant_id: str = Field(
        default="default",
        alias="BILLING_PREPAID_TENANT_ID",
    )
    billing_min_balance_new_trade_usd: str = Field(
        default="50",
        alias="BILLING_MIN_BALANCE_NEW_TRADE_USD",
    )
    strategy_require_telegram: bool = Field(
        default=False,
        alias="STRATEGY_REQUIRE_TELEGRAM",
        description="Auto-Trades nur wenn app.customer_telegram_binding fuer BILLING_PREPAID_TENANT_ID existiert.",
    )
    paper_broker_ready_allow_metadata_degraded: bool = Field(
        default=False,
        alias="PAPER_BROKER_READY_ALLOW_METADATA_DEGRADED",
        description="Lokal: /ready akzeptiert instrument_metadata-Status 'degraded'. In Production false lassen.",
    )

    @field_validator("paper_default_margin_mode")
    @classmethod
    def _margin_mode(cls, v: str) -> str:
        x = v.strip().lower()
        if x not in ("isolated", "crossed"):
            raise ValueError("PAPER_DEFAULT_MARGIN_MODE muss isolated oder crossed sein")
        return x

    @field_validator("paper_broker_port")
    @classmethod
    def _port(cls, v: int) -> int:
        if not 1 <= v <= 65535:
            raise ValueError("PAPER_BROKER_PORT ungueltig")
        return v

    @field_validator("paper_orderbook_levels")
    @classmethod
    def _ob_levels(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("PAPER_ORDERBOOK_LEVELS 1..50")
        return v

    @field_validator("bitget_market_family", mode="before")
    @classmethod
    def _market_family(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        return normalized or None

    @field_validator("bitget_margin_account_mode", mode="before")
    @classmethod
    def _margin_account_mode(cls, v: str | None) -> str | None:
        if v is None:
            return None
        normalized = v.strip().lower()
        return normalized or None

    @field_validator("bitget_product_type", "paper_default_symbol", mode="before")
    @classmethod
    def _strip_upper_optional(cls, v: str | None) -> str:
        if v is None:
            return ""
        return v.strip().upper()

    @field_validator("paper_default_leverage")
    @classmethod
    def _paper_default_leverage(cls, v: int) -> int:
        if v < 7 or v > 75:
            raise ValueError("PAPER_DEFAULT_LEVERAGE muss im Bereich 7..75 liegen")
        return v

    @field_validator("paper_max_leverage")
    @classmethod
    def _paper_max_leverage(cls, v: int) -> int:
        if v < 7 or v > 75:
            raise ValueError("PAPER_MAX_LEVERAGE muss im Bereich 7..75 liegen")
        return v

    @field_validator("stop_trigger_type_default", "tp_trigger_type_default")
    @classmethod
    def _trigger_types(cls, v: TriggerType) -> TriggerType:
        x = v.strip()
        if x not in ("mark_price", "fill_price"):
            raise ValueError("Trigger-Typ muss mark_price oder fill_price sein")
        return x

    @field_validator("strategy_registry_event_stream")
    @classmethod
    def _reg_stream_pb(cls, v: str) -> str:
        allowed = "events:strategy_registry_updated"
        x = v.strip()
        if x != allowed:
            raise ValueError(f"STRATEGY_REGISTRY_EVENT_STREAM muss {allowed!r} sein")
        return x

    @field_validator("leverage_min_liquidation_buffer_bps")
    @classmethod
    def _positive_strategy_projection_thresholds(cls, v: str) -> str:
        if Decimal(str(v)) <= 0:
            raise ValueError("Strategy-Projektions-Schwellen muessen > 0 sein")
        return str(v)

    @field_validator("exit_break_even_after_tp_index")
    @classmethod
    def _validate_break_even_index(cls, value: int) -> int:
        if value < 0 or value > 2:
            raise ValueError("EXIT_BREAK_EVEN_AFTER_TP_INDEX muss im Bereich 0..2 liegen")
        return value

    @model_validator(mode="after")
    def _validate_leverage_bounds(self) -> "PaperBrokerSettings":
        if self.paper_default_leverage > self.paper_max_leverage:
            raise ValueError(
                "PAPER_DEFAULT_LEVERAGE darf PAPER_MAX_LEVERAGE nicht uebersteigen"
            )
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
        if not self.paper_default_symbol:
            object.__setattr__(
                self,
                "paper_default_symbol",
                self.default_operational_symbol(),
            )
        if not self.paper_default_symbol:
            raise ValueError(
                "PAPER_DEFAULT_SYMBOL fehlt und konnte nicht aus Watchlist/Universe/Allowlist abgeleitet werden"
            )
        return self

    @property
    def strat_min_signal_strength(self) -> int:
        return int(self.risk_min_signal_strength)

    @property
    def strat_min_probability(self) -> float:
        return float(self.risk_min_probability)

    @property
    def strat_min_risk_score(self) -> int:
        return int(self.risk_min_risk_score)

    @property
    def strat_min_expected_return_bps(self) -> float:
        return float(self.risk_min_expected_return_bps)

    @property
    def strat_max_expected_mae_bps(self) -> float:
        return float(self.risk_max_expected_mae_bps)

    @property
    def strat_min_projected_rr(self) -> float:
        return float(self.risk_min_projected_rr)

    @property
    def max_concurrent_positions(self) -> int:
        return int(self.risk_max_concurrent_positions)

    @property
    def leverage_max_margin_usage_pct(self) -> float:
        return float(self.risk_max_account_margin_usage)

    @property
    def strategy_exec_mode(self) -> StrategyExecutionMode:
        return self.strategy_execution_mode

    @property
    def endpoint_profile(self):
        return endpoint_profile_for(
            self.bitget_market_family,
            margin_account_mode=self.bitget_margin_account_mode,
        )

    @property
    def rest_product_type_param(self) -> str | None:
        if self.bitget_market_family != "futures":
            return None
        return self.bitget_product_type.lower()

    @property
    def public_ws_inst_type(self) -> str:
        if self.bitget_market_family == "futures":
            return self.bitget_product_type
        return self.endpoint_profile.public_ws_inst_type

    def candle_granularity(self, timeframe: str) -> str:
        return self.endpoint_profile.rest_candle_granularity(timeframe)

    def instrument_identity(self, *, symbol: str | None = None) -> BitgetInstrumentIdentity:
        return BitgetInstrumentIdentity(
            market_family=self.bitget_market_family,
            symbol=symbol or self.paper_default_symbol,
            product_type=self.bitget_product_type if self.bitget_market_family == "futures" else None,
            margin_account_mode=self.bitget_margin_account_mode,
            public_ws_inst_type=self.public_ws_inst_type,
            private_ws_inst_type=self.endpoint_profile.private_ws_inst_type or self.public_ws_inst_type,
            metadata_source="paper_broker.runtime_config",
            metadata_verified=False,
            supports_funding=self.endpoint_profile.supports_funding,
            supports_open_interest=self.endpoint_profile.supports_open_interest,
            supports_long_short=self.endpoint_profile.supports_long_short,
            supports_shorting=self.endpoint_profile.supports_shorting,
            supports_reduce_only=self.endpoint_profile.supports_reduce_only,
            supports_leverage=self.endpoint_profile.supports_leverage,
            uses_spot_public_market_data=self.endpoint_profile.uses_spot_public_market_data,
        )
