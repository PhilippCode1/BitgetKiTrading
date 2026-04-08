from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MarketFamily = Literal["spot", "margin", "futures"]
MarginAccountMode = Literal["cash", "isolated", "crossed"]
CatalogSnapshotStatus = Literal["ok", "partial", "error"]
MARKET_UNIVERSE_SCHEMA_VERSION = "bitget-market-universe-v1"

_SPOT_GRANULARITY_MAP = {
    "1m": "1min",
    "3m": "3min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1H": "1h",
    "4H": "4h",
    "6H": "6h",
    "12H": "12h",
    "1D": "1day",
    "1W": "1week",
    "1M": "1M",
}


def market_category_key(
    *,
    venue: str,
    market_family: MarketFamily,
    product_type: str | None,
    margin_account_mode: MarginAccountMode,
) -> str:
    product = product_type or margin_account_mode
    return f"{venue}:{market_family}:{product}"


def _normalize_capability_pair(
    *,
    supports_shorting: bool,
    supports_long_short: bool,
) -> tuple[bool, bool]:
    normalized = bool(supports_shorting or supports_long_short)
    return normalized, normalized


def normalize_market_eligibility_flags(
    *,
    inventory_visible: bool,
    analytics_eligible: bool,
    paper_shadow_eligible: bool,
    live_execution_enabled: bool,
    execution_disabled: bool,
) -> tuple[bool, bool, bool, bool, bool]:
    inventory = bool(
        inventory_visible or analytics_eligible or paper_shadow_eligible or live_execution_enabled
    )
    analytics = bool(analytics_eligible or paper_shadow_eligible or live_execution_enabled) and inventory
    paper_shadow = bool(paper_shadow_eligible or live_execution_enabled) and analytics
    live_enabled = bool(live_execution_enabled) and paper_shadow
    execution_off = bool(execution_disabled) or (inventory and analytics and not live_enabled)
    return inventory, analytics, paper_shadow, live_enabled, execution_off


class BitgetEndpointProfile(BaseModel):
    market_family: MarketFamily
    public_symbol_config_path: str
    public_ticker_path: str
    public_candles_path: str
    public_trades_path: str
    public_depth_path: str | None = None
    public_open_interest_path: str | None = None
    public_funding_path: str | None = None
    private_place_order_path: str | None = None
    private_cancel_order_path: str | None = None
    private_modify_order_path: str | None = None
    private_order_detail_path: str | None = None
    private_open_orders_path: str | None = None
    private_cancel_all_orders_path: str | None = None
    private_account_assets_path: str | None = None
    private_positions_path: str | None = None
    private_order_history_path: str | None = None
    private_fill_history_path: str | None = None
    private_set_leverage_path: str | None = None
    public_ws_inst_type: str
    private_ws_inst_type: str | None = None
    default_margin_account_mode: MarginAccountMode = "cash"
    quantity_field: str = "size"
    market_buy_quantity_field: str = "size"
    supports_funding: bool = False
    supports_open_interest: bool = False
    supports_long_short: bool = False
    supports_shorting: bool = False
    supports_reduce_only: bool = False
    supports_leverage: bool = False
    uses_spot_public_market_data: bool = False

    @field_validator(
        "public_symbol_config_path",
        "public_ticker_path",
        "public_candles_path",
        "public_trades_path",
        "public_depth_path",
        "public_open_interest_path",
        "public_funding_path",
        "private_place_order_path",
        "private_cancel_order_path",
        "private_modify_order_path",
        "private_order_detail_path",
        "private_open_orders_path",
        "private_cancel_all_orders_path",
        "private_account_assets_path",
        "private_positions_path",
        "private_order_history_path",
        "private_fill_history_path",
        "private_set_leverage_path",
        mode="before",
    )
    @classmethod
    def _normalize_paths(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @model_validator(mode="after")
    def _normalize_capabilities(self) -> "BitgetEndpointProfile":
        supports_shorting, supports_long_short = _normalize_capability_pair(
            supports_shorting=self.supports_shorting,
            supports_long_short=self.supports_long_short,
        )
        object.__setattr__(self, "supports_shorting", supports_shorting)
        object.__setattr__(self, "supports_long_short", supports_long_short)
        return self

    def rest_candle_granularity(self, timeframe: str) -> str:
        if self.market_family == "futures":
            return timeframe
        return _SPOT_GRANULARITY_MAP.get(timeframe, timeframe)


class BitgetMarketCapabilityMatrixRow(BaseModel):
    schema_version: str = MARKET_UNIVERSE_SCHEMA_VERSION
    venue: str = "bitget"
    market_family: MarketFamily
    product_type: str | None = None
    margin_account_mode: MarginAccountMode = "cash"
    category_key: str | None = None
    metadata_source: str = "runtime_config"
    metadata_verified: bool = False
    inventory_visible: bool = False
    analytics_eligible: bool = False
    paper_shadow_eligible: bool = False
    live_execution_enabled: bool = False
    execution_disabled: bool = False
    supports_funding: bool = False
    supports_open_interest: bool = False
    supports_long_short: bool = False
    supports_shorting: bool = False
    supports_reduce_only: bool = False
    supports_leverage: bool = False
    uses_spot_public_market_data: bool = False
    instrument_count: int = 0
    tradeable_instrument_count: int = 0
    subscribable_instrument_count: int = 0
    metadata_verified_count: int = 0
    sample_symbols: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)

    @field_validator(
        "venue",
        "market_family",
        "product_type",
        "metadata_source",
        "category_key",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object, info) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if info.field_name in {"market_family"}:
            return normalized.lower()
        if info.field_name in {"product_type"}:
            return normalized.upper()
        return normalized

    @field_validator("sample_symbols", mode="before")
    @classmethod
    def _normalize_sample_symbols(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        out: list[str] = []
        for item in value:
            normalized = str(item).strip().upper()
            if normalized and normalized not in out:
                out.append(normalized)
        return out

    @field_validator("reasons", mode="before")
    @classmethod
    def _normalize_reasons(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        out: list[str] = []
        for item in value:
            normalized = str(item).strip()
            if normalized and normalized not in out:
                out.append(normalized)
        return out

    @model_validator(mode="after")
    def _finalize_category_row(self) -> "BitgetMarketCapabilityMatrixRow":
        if self.market_family == "futures" and not self.product_type:
            raise ValueError("Futures-Kategorien brauchen product_type")
        if self.market_family == "spot":
            object.__setattr__(self, "margin_account_mode", "cash")
        if not self.category_key:
            object.__setattr__(
                self,
                "category_key",
                market_category_key(
                    venue=self.venue,
                    market_family=self.market_family,
                    product_type=self.product_type,
                    margin_account_mode=self.margin_account_mode,
                ),
            )
        supports_shorting, supports_long_short = _normalize_capability_pair(
            supports_shorting=self.supports_shorting,
            supports_long_short=self.supports_long_short,
        )
        object.__setattr__(self, "supports_shorting", supports_shorting)
        object.__setattr__(self, "supports_long_short", supports_long_short)
        inventory, analytics, paper_shadow, live_enabled, execution_off = (
            normalize_market_eligibility_flags(
                inventory_visible=self.inventory_visible,
                analytics_eligible=self.analytics_eligible,
                paper_shadow_eligible=self.paper_shadow_eligible,
                live_execution_enabled=self.live_execution_enabled,
                execution_disabled=self.execution_disabled,
            )
        )
        object.__setattr__(self, "inventory_visible", inventory)
        object.__setattr__(self, "analytics_eligible", analytics)
        object.__setattr__(self, "paper_shadow_eligible", paper_shadow)
        object.__setattr__(self, "live_execution_enabled", live_enabled)
        object.__setattr__(self, "execution_disabled", execution_off)
        return self


class BitgetInstrumentIdentity(BaseModel):
    schema_version: str = MARKET_UNIVERSE_SCHEMA_VERSION
    venue: str = "bitget"
    market_family: MarketFamily
    symbol: str
    canonical_instrument_id: str | None = None
    category_key: str | None = None
    product_type: str | None = None
    margin_coin: str | None = None
    margin_account_mode: MarginAccountMode = "cash"
    base_coin: str | None = None
    quote_coin: str | None = None
    settle_coin: str | None = None
    public_ws_inst_type: str
    private_ws_inst_type: str | None = None
    metadata_source: str = "runtime_config"
    metadata_verified: bool = False
    status: str | None = None
    inventory_visible: bool = False
    analytics_eligible: bool = False
    paper_shadow_eligible: bool = False
    live_execution_enabled: bool = False
    execution_disabled: bool = False
    supports_funding: bool = False
    supports_open_interest: bool = False
    supports_long_short: bool = False
    supports_shorting: bool = False
    supports_reduce_only: bool = False
    supports_leverage: bool = False
    uses_spot_public_market_data: bool = False

    @field_validator(
        "venue",
        "market_family",
        "symbol",
        "canonical_instrument_id",
        "category_key",
        "product_type",
        "margin_coin",
        "base_coin",
        "quote_coin",
        "settle_coin",
        "public_ws_inst_type",
        "private_ws_inst_type",
        "metadata_source",
        "status",
        mode="before",
    )
    @classmethod
    def _normalize_text(cls, value: object, info) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if info.field_name in {
            "symbol",
            "product_type",
            "margin_coin",
            "base_coin",
            "quote_coin",
            "settle_coin",
            "public_ws_inst_type",
            "private_ws_inst_type",
        }:
            return normalized.upper()
        if info.field_name == "market_family":
            return normalized.lower()
        return normalized

    @model_validator(mode="after")
    def _validate_identity(self) -> "BitgetInstrumentIdentity":
        if "_" in self.symbol:
            raise ValueError("Bitget-Instrumente muessen v2-Symbole ohne Suffix verwenden")
        if self.market_family == "futures":
            if not self.product_type:
                raise ValueError("Futures-Instrumente brauchen product_type")
            if self.margin_account_mode == "cash":
                object.__setattr__(self, "margin_account_mode", "isolated")
        if self.market_family == "spot":
            object.__setattr__(self, "margin_account_mode", "cash")
        if not self.category_key:
            object.__setattr__(
                self,
                "category_key",
                market_category_key(
                    venue=self.venue,
                    market_family=self.market_family,
                    product_type=self.product_type,
                    margin_account_mode=self.margin_account_mode,
                ),
            )
        if not self.canonical_instrument_id:
            object.__setattr__(self, "canonical_instrument_id", self.instrument_key)
        supports_shorting, supports_long_short = _normalize_capability_pair(
            supports_shorting=self.supports_shorting,
            supports_long_short=self.supports_long_short,
        )
        object.__setattr__(self, "supports_shorting", supports_shorting)
        object.__setattr__(self, "supports_long_short", supports_long_short)
        inventory, analytics, paper_shadow, live_enabled, execution_off = (
            normalize_market_eligibility_flags(
                inventory_visible=self.inventory_visible,
                analytics_eligible=self.analytics_eligible,
                paper_shadow_eligible=self.paper_shadow_eligible,
                live_execution_enabled=self.live_execution_enabled,
                execution_disabled=self.execution_disabled,
            )
        )
        object.__setattr__(self, "inventory_visible", inventory)
        object.__setattr__(self, "analytics_eligible", analytics)
        object.__setattr__(self, "paper_shadow_eligible", paper_shadow)
        object.__setattr__(self, "live_execution_enabled", live_enabled)
        object.__setattr__(self, "execution_disabled", execution_off)
        return self

    @property
    def instrument_key(self) -> str:
        product = self.product_type or self.margin_account_mode
        return f"{self.venue}:{self.market_family}:{product}:{self.symbol}"

    def capability_matrix_row(self) -> BitgetMarketCapabilityMatrixRow:
        return BitgetMarketCapabilityMatrixRow(
            venue=self.venue,
            market_family=self.market_family,
            product_type=self.product_type,
            margin_account_mode=self.margin_account_mode,
            category_key=self.category_key,
            metadata_source=self.metadata_source,
            metadata_verified=self.metadata_verified,
            inventory_visible=self.inventory_visible,
            analytics_eligible=self.analytics_eligible,
            paper_shadow_eligible=self.paper_shadow_eligible,
            live_execution_enabled=self.live_execution_enabled,
            execution_disabled=self.execution_disabled,
            supports_funding=self.supports_funding,
            supports_open_interest=self.supports_open_interest,
            supports_long_short=self.supports_long_short,
            supports_shorting=self.supports_shorting,
            supports_reduce_only=self.supports_reduce_only,
            supports_leverage=self.supports_leverage,
            uses_spot_public_market_data=self.uses_spot_public_market_data,
            metadata_verified_count=1 if self.metadata_verified else 0,
            sample_symbols=[self.symbol],
        )


class BitgetInstrumentCatalogEntry(BitgetInstrumentIdentity):
    symbol_aliases: list[str] = Field(default_factory=list)
    price_tick_size: str | None = None
    quantity_step: str | None = None
    quantity_min: str | None = None
    quantity_max: str | None = None
    market_order_quantity_max: str | None = None
    min_notional_quote: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    quote_precision: int | None = None
    leverage_min: int | None = None
    leverage_max: int | None = None
    funding_interval_hours: int | None = None
    symbol_type: str | None = None
    supported_margin_coins: list[str] = Field(default_factory=list)
    trading_status: str = "unknown"
    trading_enabled: bool = False
    subscribe_enabled: bool = False
    session_metadata: dict[str, Any] = Field(default_factory=dict)
    refresh_ts_ms: int | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol_aliases", mode="before")
    @classmethod
    def _normalize_aliases(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        deduped: list[str] = []
        for item in value:
            normalized = str(item).strip().upper()
            if normalized and normalized not in deduped:
                deduped.append(normalized)
        return deduped

    @field_validator(
        "price_tick_size",
        "quantity_step",
        "quantity_min",
        "quantity_max",
        "market_order_quantity_max",
        "min_notional_quote",
        mode="before",
    )
    @classmethod
    def _normalize_numeric_text(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("supported_margin_coins", mode="before")
    @classmethod
    def _normalize_margin_coin_list(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        out: list[str] = []
        for item in value:
            normalized = str(item).strip().upper()
            if normalized and normalized not in out:
                out.append(normalized)
        return out

    @field_validator("trading_status", mode="before")
    @classmethod
    def _normalize_trading_status(cls, value: object) -> object:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return normalized or "unknown"

    @model_validator(mode="after")
    def _finalize_catalog_entry(self) -> "BitgetInstrumentCatalogEntry":
        aliases = list(self.symbol_aliases)
        if self.symbol not in aliases:
            aliases.insert(0, self.symbol)
        object.__setattr__(self, "symbol_aliases", aliases)
        return self

    def identity(self) -> BitgetInstrumentIdentity:
        return BitgetInstrumentIdentity(
            venue=self.venue,
            market_family=self.market_family,
            symbol=self.symbol,
            canonical_instrument_id=self.canonical_instrument_id,
            category_key=self.category_key,
            product_type=self.product_type,
            margin_coin=self.margin_coin,
            margin_account_mode=self.margin_account_mode,
            base_coin=self.base_coin,
            quote_coin=self.quote_coin,
            settle_coin=self.settle_coin,
            public_ws_inst_type=self.public_ws_inst_type,
            private_ws_inst_type=self.private_ws_inst_type,
            metadata_source=self.metadata_source,
            metadata_verified=self.metadata_verified,
            status=self.status,
            inventory_visible=self.inventory_visible,
            analytics_eligible=self.analytics_eligible,
            paper_shadow_eligible=self.paper_shadow_eligible,
            live_execution_enabled=self.live_execution_enabled,
            execution_disabled=self.execution_disabled,
            supports_funding=self.supports_funding,
            supports_open_interest=self.supports_open_interest,
            supports_long_short=self.supports_long_short,
            supports_shorting=self.supports_shorting,
            supports_reduce_only=self.supports_reduce_only,
            supports_leverage=self.supports_leverage,
            uses_spot_public_market_data=self.uses_spot_public_market_data,
        )


class BitgetInstrumentCatalogSnapshot(BaseModel):
    schema_version: str = MARKET_UNIVERSE_SCHEMA_VERSION
    snapshot_id: str
    source_service: str
    refresh_reason: str
    status: CatalogSnapshotStatus = "ok"
    fetch_started_ts_ms: int
    fetch_completed_ts_ms: int | None = None
    refreshed_families: list[str] = Field(default_factory=list)
    counts_by_family: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    capability_matrix: list[BitgetMarketCapabilityMatrixRow] = Field(default_factory=list)
    entries: list[BitgetInstrumentCatalogEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _finalize_snapshot(self) -> "BitgetInstrumentCatalogSnapshot":
        if not self.counts_by_family:
            counts: dict[str, int] = {}
            for entry in self.entries:
                counts[entry.market_family] = counts.get(entry.market_family, 0) + 1
            object.__setattr__(self, "counts_by_family", counts)
        if not self.capability_matrix:
            object.__setattr__(self, "capability_matrix", build_capability_matrix(self.entries))
        return self


def build_capability_matrix(
    entries: Sequence[BitgetInstrumentCatalogEntry],
    *,
    category_descriptors: Sequence[BitgetMarketCapabilityMatrixRow] | None = None,
) -> list[BitgetMarketCapabilityMatrixRow]:
    rows: dict[str, BitgetMarketCapabilityMatrixRow] = {}
    for descriptor in category_descriptors or ():
        validated = BitgetMarketCapabilityMatrixRow.model_validate(
            descriptor.model_dump(mode="json")
        )
        rows[validated.category_key or ""] = validated
    for entry in entries:
        key = entry.category_key or market_category_key(
            venue=entry.venue,
            market_family=entry.market_family,
            product_type=entry.product_type,
            margin_account_mode=entry.margin_account_mode,
        )
        row = rows.get(key)
        if row is None:
            row = BitgetMarketCapabilityMatrixRow(
                venue=entry.venue,
                market_family=entry.market_family,
                product_type=entry.product_type,
                margin_account_mode=entry.margin_account_mode,
                category_key=key,
                metadata_source=entry.metadata_source,
                metadata_verified=entry.metadata_verified,
                inventory_visible=entry.inventory_visible,
                analytics_eligible=entry.analytics_eligible,
                paper_shadow_eligible=entry.paper_shadow_eligible,
                live_execution_enabled=entry.live_execution_enabled,
                execution_disabled=entry.execution_disabled,
                supports_funding=entry.supports_funding,
                supports_open_interest=entry.supports_open_interest,
                supports_long_short=entry.supports_long_short,
                supports_shorting=entry.supports_shorting,
                supports_reduce_only=entry.supports_reduce_only,
                supports_leverage=entry.supports_leverage,
                uses_spot_public_market_data=entry.uses_spot_public_market_data,
            )
            rows[key] = row
        else:
            row.metadata_verified = row.metadata_verified or entry.metadata_verified
            row.inventory_visible = row.inventory_visible or entry.inventory_visible
            row.analytics_eligible = row.analytics_eligible or entry.analytics_eligible
            row.paper_shadow_eligible = row.paper_shadow_eligible or entry.paper_shadow_eligible
            row.live_execution_enabled = row.live_execution_enabled or entry.live_execution_enabled
            row.execution_disabled = row.execution_disabled or entry.execution_disabled
            row.supports_funding = row.supports_funding or entry.supports_funding
            row.supports_open_interest = row.supports_open_interest or entry.supports_open_interest
            row.supports_long_short = row.supports_long_short or entry.supports_long_short
            row.supports_shorting = row.supports_shorting or entry.supports_shorting
            row.supports_reduce_only = row.supports_reduce_only or entry.supports_reduce_only
            row.supports_leverage = row.supports_leverage or entry.supports_leverage
            row.uses_spot_public_market_data = (
                row.uses_spot_public_market_data or entry.uses_spot_public_market_data
            )
            if (
                row.metadata_source == "runtime_config"
                and entry.metadata_source
                and entry.metadata_source != "runtime_config"
            ):
                row.metadata_source = entry.metadata_source
        row.instrument_count += 1
        if entry.trading_enabled:
            row.tradeable_instrument_count += 1
        if entry.subscribe_enabled:
            row.subscribable_instrument_count += 1
        if entry.metadata_verified:
            row.metadata_verified_count += 1
        if entry.symbol not in row.sample_symbols and len(row.sample_symbols) < 5:
            row.sample_symbols.append(entry.symbol)
    finalized = [
        BitgetMarketCapabilityMatrixRow.model_validate(row.model_dump(mode="json"))
        for row in rows.values()
    ]
    return sorted(
        finalized,
        key=lambda row: (
            row.market_family,
            row.product_type or "",
            row.margin_account_mode,
            row.category_key or "",
        ),
    )


def trading_status_allows_trading(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {"normal", "listed", "online", "account_visible"}


def trading_status_allows_subscription(status: str) -> bool:
    normalized = str(status or "").strip().lower()
    return normalized in {
        "normal",
        "listed",
        "online",
        "gray",
        "limit_open",
        "restrictedapi",
        "account_visible",
    }


def endpoint_profile_for(
    market_family: MarketFamily,
    *,
    margin_account_mode: MarginAccountMode = "cash",
) -> BitgetEndpointProfile:
    if market_family == "futures":
        return BitgetEndpointProfile(
            market_family="futures",
            public_symbol_config_path="/api/v2/mix/market/contracts",
            public_ticker_path="/api/v2/mix/market/symbol-price",
            public_candles_path="/api/v2/mix/market/candles",
            public_trades_path="/api/v2/mix/market/fills-history",
            public_depth_path="/api/v2/mix/market/merge-depth",
            public_open_interest_path="/api/v2/mix/market/open-interest",
            public_funding_path="/api/v2/mix/market/current-fund-rate",
            private_place_order_path="/api/v2/mix/order/place-order",
            private_cancel_order_path="/api/v2/mix/order/cancel-order",
            private_modify_order_path="/api/v2/mix/order/modify-order",
            private_order_detail_path="/api/v2/mix/order/detail",
            private_open_orders_path="/api/v2/mix/order/orders-pending",
            private_cancel_all_orders_path="/api/v2/mix/order/cancel-all-orders",
            private_order_history_path="/api/v2/mix/order/orders-history",
            private_fill_history_path="/api/v2/mix/order/fill-history",
            private_set_leverage_path="/api/v2/mix/account/set-leverage",
            private_account_assets_path="/api/v2/mix/account/account",
            private_positions_path="/api/v2/mix/position/all-position",
            public_ws_inst_type="FUTURES",
            private_ws_inst_type="FUTURES",
            default_margin_account_mode="isolated",
            quantity_field="size",
            market_buy_quantity_field="size",
            supports_funding=True,
            supports_open_interest=True,
            supports_long_short=True,
            supports_shorting=True,
            supports_reduce_only=True,
            supports_leverage=True,
        )
    if market_family == "spot":
        return BitgetEndpointProfile(
            market_family="spot",
            public_symbol_config_path="/api/v2/spot/public/symbols",
            public_ticker_path="/api/v2/spot/market/tickers",
            public_candles_path="/api/v2/spot/market/candles",
            public_trades_path="/api/v2/spot/market/fills",
            private_place_order_path="/api/v2/spot/trade/place-order",
            private_cancel_order_path="/api/v2/spot/trade/cancel-order",
            private_order_detail_path="/api/v2/spot/trade/orderInfo",
            private_open_orders_path="/api/v2/spot/trade/unfilled-orders",
            private_order_history_path="/api/v2/spot/trade/history-orders",
            private_fill_history_path="/api/v2/spot/trade/fills",
            private_account_assets_path="/api/v2/spot/account/assets",
            public_ws_inst_type="SPOT",
            quantity_field="size",
            market_buy_quantity_field="size",
            supports_reduce_only=False,
            supports_long_short=False,
            supports_shorting=False,
            supports_leverage=False,
        )
    if margin_account_mode == "crossed":
        return BitgetEndpointProfile(
            market_family="margin",
            public_symbol_config_path="/api/v2/spot/public/symbols",
            public_ticker_path="/api/v2/spot/market/tickers",
            public_candles_path="/api/v2/spot/market/candles",
            public_trades_path="/api/v2/spot/market/fills",
            private_place_order_path="/api/v2/margin/crossed/place-order",
            private_cancel_order_path="/api/v2/margin/crossed/cancel-order",
            private_account_assets_path="/api/v2/margin/crossed/account/assets",
            public_ws_inst_type="SPOT",
            private_ws_inst_type="MARGIN",
            default_margin_account_mode="crossed",
            quantity_field="baseSize",
            market_buy_quantity_field="quoteSize",
            supports_reduce_only=False,
            supports_long_short=True,
            supports_shorting=True,
            supports_leverage=True,
            uses_spot_public_market_data=True,
        )
    return BitgetEndpointProfile(
        market_family="margin",
        public_symbol_config_path="/api/v2/spot/public/symbols",
        public_ticker_path="/api/v2/spot/market/tickers",
        public_candles_path="/api/v2/spot/market/candles",
        public_trades_path="/api/v2/spot/market/fills",
        private_place_order_path="/api/v2/margin/isolated/place-order",
        private_cancel_order_path="/api/v2/margin/isolated/cancel-order",
        private_open_orders_path="/api/v2/margin/isolated/open-orders",
        private_account_assets_path="/api/v2/margin/isolated/account/assets",
        public_ws_inst_type="SPOT",
        private_ws_inst_type="MARGIN",
        default_margin_account_mode="isolated",
        quantity_field="baseSize",
        market_buy_quantity_field="quoteSize",
        supports_reduce_only=False,
        supports_long_short=True,
        supports_shorting=True,
        supports_leverage=True,
        uses_spot_public_market_data=True,
    )
