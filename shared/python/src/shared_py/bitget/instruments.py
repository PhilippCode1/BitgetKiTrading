from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MarketFamily = Literal["spot", "margin", "futures"]
MarginAccountMode = Literal["cash", "isolated", "crossed"]
CatalogSnapshotStatus = Literal["ok", "partial", "error"]
AssetUniverseStatus = Literal[
    "unknown",
    "discovered",
    "active",
    "watchlist",
    "shadow_allowed",
    "live_candidate",
    "live_allowed",
    "quarantined",
    "delisted",
    "suspended",
    "blocked",
]
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
    public_orderbook_resync_path: str | None = None
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
    maintenance_margin_rate_0_1: float | None = None

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
            maintenance_margin_rate_0_1=self.maintenance_margin_rate_0_1,
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
            public_orderbook_resync_path="/api/v2/mix/market/depth",
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


def _bitget_metadata_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _bitget_metadata_optional_mmr_0_1(row: dict[str, Any]) -> float | None:
    """Gewuenschte Rate 0..1; Werte >1 werden als Prozent (z.B. 0.4 fuer 0.4%) gelesen."""
    for key in (
        "maintenanceRate",
        "maintainMarginRate",
        "maintenanceMarginRate",
        "maintainMargin",
        "mmr",
    ):
        v = row.get(key)
        if v in (None, ""):
            continue
        try:
            f = float(str(v).strip())
        except ValueError:
            continue
        if f > 1.0:
            f = f / 100.0
        return f if f >= 0.0 else None
    return None


def _bitget_spot_tick_size_from_row(row: dict[str, Any]) -> str | None:
    precision = _bitget_metadata_optional_int(row.get("pricePrecision"))
    if precision is None:
        return None
    return format(10 ** (-precision), "f")


def _bitget_spot_quantity_step_from_row(row: dict[str, Any]) -> str | None:
    precision = _bitget_metadata_optional_int(row.get("quantityPrecision"))
    if precision is None:
        return None
    return format(10 ** (-precision), "f")


def _catalog_eligibility_flags(
    *,
    trading_enabled: bool,
    subscribe_enabled: bool,
    execution_adapter_available: bool,
) -> dict[str, bool]:
    inventory_visible = True
    analytics_eligible = bool(subscribe_enabled)
    paper_shadow_eligible = bool(trading_enabled and execution_adapter_available)
    live_execution_enabled = bool(trading_enabled and execution_adapter_available)
    execution_disabled = inventory_visible and analytics_eligible and not live_execution_enabled
    return {
        "inventory_visible": inventory_visible,
        "analytics_eligible": analytics_eligible,
        "paper_shadow_eligible": paper_shadow_eligible,
        "live_execution_enabled": live_execution_enabled,
        "execution_disabled": execution_disabled,
        "trading_enabled": bool(trading_enabled),
        "subscribe_enabled": bool(subscribe_enabled),
    }


def _first_margin_coin_list_value(value: object) -> str | None:
    if isinstance(value, list):
        for item in value:
            normalized = str(item).strip().upper()
            if normalized:
                return normalized
    return None


class MarketInstrument(BaseModel):
    """
    Instanziierte, familienübergreifende API-Sicht auf Katalog-Metadaten.
    `product_family` entspricht dem internen `market_family` (Spot, Margin, Futures).
    `lot_size` spiegelt `quantity_step` (Kontingent-/Los-Schritt), ohne stillen Default.
    """

    schema_version: str = Field(default=MARKET_UNIVERSE_SCHEMA_VERSION)
    venue: str = "bitget"
    product_family: MarketFamily
    symbol: str
    canonical_instrument_id: str | None = None
    category_key: str | None = None
    product_type: str | None = None
    margin_account_mode: MarginAccountMode = "cash"
    margin_coin: str | None = None
    base_coin: str | None = None
    quote_coin: str | None = None
    settle_coin: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    lot_size: str | None = None
    price_tick_size: str | None = None
    trading_status: str = "unknown"
    metadata_verified: bool = False
    metadata_source: str = "runtime_config"
    public_ws_inst_type: str
    private_ws_inst_type: str | None = None

    @field_validator("product_family", mode="before")
    @classmethod
    def _pf(cls, v: object) -> object:
        if v is None:
            return v
        s = str(v).strip().lower()
        return s or v

    @field_validator("symbol", mode="before")
    @classmethod
    def _sym(cls, v: object) -> str:
        return str(v or "").strip().upper()

    @classmethod
    def from_catalog_entry(cls, entry: BitgetInstrumentCatalogEntry) -> "MarketInstrument":
        return cls(
            venue=entry.venue,
            product_family=entry.market_family,
            symbol=entry.symbol,
            canonical_instrument_id=entry.canonical_instrument_id,
            category_key=entry.category_key,
            product_type=entry.product_type,
            margin_account_mode=entry.margin_account_mode,
            margin_coin=entry.margin_coin,
            base_coin=entry.base_coin,
            quote_coin=entry.quote_coin,
            settle_coin=entry.settle_coin,
            price_precision=entry.price_precision,
            quantity_precision=entry.quantity_precision,
            lot_size=entry.quantity_step,
            price_tick_size=entry.price_tick_size,
            trading_status=entry.trading_status,
            metadata_verified=entry.metadata_verified,
            metadata_source=entry.metadata_source,
            public_ws_inst_type=entry.public_ws_inst_type,
            private_ws_inst_type=entry.private_ws_inst_type,
        )


class MarketInstrumentFactory:
    """Baut `BitgetInstrumentCatalogEntry` aus Bitget-REST-Zeilen und `MarketInstrument` aus Katalog."""

    @staticmethod
    def from_catalog_entry(entry: BitgetInstrumentCatalogEntry) -> MarketInstrument:
        return MarketInstrument.from_catalog_entry(entry)

    @staticmethod
    def catalog_entry_from_spot_row(
        row: dict[str, Any], *, refresh_ts_ms: int | None = None
    ) -> BitgetInstrumentCatalogEntry | None:
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            return None
        profile = endpoint_profile_for("spot")
        trading_status = str(row.get("status") or "unknown").strip().lower() or "unknown"
        eflags = _catalog_eligibility_flags(
            trading_enabled=trading_status_allows_trading(trading_status),
            subscribe_enabled=trading_status_allows_subscription(trading_status),
            execution_adapter_available=profile.private_place_order_path is not None,
        )
        rts = refresh_ts_ms if refresh_ts_ms is not None else int(time.time() * 1000)
        return BitgetInstrumentCatalogEntry(
            market_family="spot",
            symbol=sym,
            symbol_aliases=[sym],
            base_coin=str(row.get("baseCoin") or "") or None,
            quote_coin=str(row.get("quoteCoin") or "") or None,
            public_ws_inst_type=profile.public_ws_inst_type,
            private_ws_inst_type=profile.public_ws_inst_type,
            metadata_source=profile.public_symbol_config_path,
            metadata_verified=True,
            status=trading_status,
            inventory_visible=eflags["inventory_visible"],
            analytics_eligible=eflags["analytics_eligible"],
            paper_shadow_eligible=eflags["paper_shadow_eligible"],
            live_execution_enabled=eflags["live_execution_enabled"],
            execution_disabled=eflags["execution_disabled"],
            trading_status=trading_status,
            trading_enabled=eflags["trading_enabled"],
            subscribe_enabled=eflags["subscribe_enabled"],
            supports_reduce_only=profile.supports_reduce_only,
            supports_long_short=profile.supports_long_short,
            supports_shorting=profile.supports_shorting,
            supports_leverage=profile.supports_leverage,
            uses_spot_public_market_data=profile.uses_spot_public_market_data,
            price_tick_size=_bitget_spot_tick_size_from_row(row),
            quantity_step=_bitget_spot_quantity_step_from_row(row),
            quantity_min=str(row.get("minTradeAmount") or "") or None,
            quantity_max=str(row.get("maxTradeAmount") or "") or None,
            min_notional_quote=str(row.get("minTradeUSDT") or "") or None,
            price_precision=_bitget_metadata_optional_int(row.get("pricePrecision")),
            quantity_precision=_bitget_metadata_optional_int(row.get("quantityPrecision")),
            quote_precision=_bitget_metadata_optional_int(row.get("quotePrecision")),
            symbol_type="spot",
            session_metadata={"schedule": "24x7", "timezone": "UTC"},
            refresh_ts_ms=rts,
            raw_metadata=row,
        )

    @staticmethod
    def catalog_entry_from_futures_row(
        row: dict[str, Any], *, refresh_ts_ms: int | None = None
    ) -> BitgetInstrumentCatalogEntry | None:
        sym = str(row.get("symbol") or "").strip().upper()
        if not sym:
            return None
        product_type = str(row.get("productType") or "").strip().upper()
        if not product_type:
            return None
        profile = endpoint_profile_for("futures")
        trading_status = (
            str(row.get("symbolStatus") or row.get("status") or "unknown").strip().lower()
            or "unknown"
        )
        eflags = _catalog_eligibility_flags(
            trading_enabled=trading_status_allows_trading(trading_status),
            subscribe_enabled=trading_status_allows_subscription(trading_status),
            execution_adapter_available=profile.private_place_order_path is not None,
        )
        margin_coin = _first_margin_coin_list_value(row.get("supportMarginCoins")) or str(
            row.get("marginCoin") or ""
        )
        session_metadata = {
            "schedule": "24x7",
            "timezone": "UTC",
            "symbol_type": str(row.get("symbolType") or "") or None,
            "off_time": _bitget_metadata_optional_int(row.get("offTime")),
            "limit_open_time": _bitget_metadata_optional_int(row.get("limitOpenTime")),
            "delivery_time": _bitget_metadata_optional_int(row.get("deliveryTime")),
            "delivery_start_time": _bitget_metadata_optional_int(row.get("deliveryStartTime")),
            "launch_time": _bitget_metadata_optional_int(row.get("launchTime")),
            "maintain_time": _bitget_metadata_optional_int(row.get("maintainTime")),
        }
        rts = refresh_ts_ms if refresh_ts_ms is not None else int(time.time() * 1000)
        return BitgetInstrumentCatalogEntry(
            market_family="futures",
            symbol=sym,
            symbol_aliases=[sym],
            product_type=product_type,
            margin_coin=margin_coin or None,
            base_coin=str(row.get("baseCoin") or "") or None,
            quote_coin=str(row.get("quoteCoin") or "") or None,
            settle_coin=str(row.get("settleCoin") or margin_coin or "") or None,
            margin_account_mode="isolated",
            public_ws_inst_type=product_type,
            private_ws_inst_type=product_type,
            metadata_source=profile.public_symbol_config_path,
            metadata_verified=True,
            status=trading_status,
            inventory_visible=eflags["inventory_visible"],
            analytics_eligible=eflags["analytics_eligible"],
            paper_shadow_eligible=eflags["paper_shadow_eligible"],
            live_execution_enabled=eflags["live_execution_enabled"],
            execution_disabled=eflags["execution_disabled"],
            trading_status=trading_status,
            trading_enabled=eflags["trading_enabled"],
            subscribe_enabled=eflags["subscribe_enabled"],
            supports_funding=profile.supports_funding,
            supports_open_interest=profile.supports_open_interest,
            supports_reduce_only=profile.supports_reduce_only,
            supports_long_short=profile.supports_long_short,
            supports_shorting=profile.supports_shorting,
            supports_leverage=profile.supports_leverage,
            price_tick_size=str(row.get("priceEndStep") or "") or None,
            quantity_step=str(row.get("sizeMultiplier") or "") or None,
            quantity_min=str(row.get("minTradeNum") or "") or None,
            quantity_max=str(row.get("maxOrderQty") or "") or None,
            market_order_quantity_max=str(row.get("maxMarketOrderQty") or "") or None,
            min_notional_quote=str(row.get("minTradeUSDT") or "") or None,
            price_precision=_bitget_metadata_optional_int(row.get("pricePlace")),
            quantity_precision=_bitget_metadata_optional_int(row.get("volumePlace")),
            leverage_min=_bitget_metadata_optional_int(row.get("minLever")),
            leverage_max=_bitget_metadata_optional_int(row.get("maxLever")),
            funding_interval_hours=_bitget_metadata_optional_int(row.get("fundInterval")),
            symbol_type=str(row.get("symbolType") or "") or None,
            supported_margin_coins=list(row.get("supportMarginCoins") or []),
            maintenance_margin_rate_0_1=_bitget_metadata_optional_mmr_0_1(row),
            session_metadata={k: v for k, v in session_metadata.items() if v is not None},
            refresh_ts_ms=rts,
            raw_metadata=row,
        )

    @staticmethod
    def catalog_entry_from_margin_spot_row(
        *,
        symbol: str,
        spot_row: dict[str, Any],
        margin_account_mode: MarginAccountMode,
        refresh_ts_ms: int | None = None,
    ) -> BitgetInstrumentCatalogEntry | None:
        sym = str(symbol).strip().upper()
        if not sym or not spot_row:
            return None
        profile = endpoint_profile_for("margin", margin_account_mode=margin_account_mode)
        spot_status = str(spot_row.get("status") or "unknown").strip().lower() or "unknown"
        trading_status = f"{spot_status}_account_visible"
        eflags = _catalog_eligibility_flags(
            trading_enabled=trading_status_allows_trading(spot_status),
            subscribe_enabled=trading_status_allows_subscription(spot_status),
            execution_adapter_available=profile.private_place_order_path is not None,
        )
        rts = refresh_ts_ms if refresh_ts_ms is not None else int(time.time() * 1000)
        return BitgetInstrumentCatalogEntry(
            market_family="margin",
            symbol=sym,
            symbol_aliases=[sym],
            margin_account_mode=margin_account_mode,
            public_ws_inst_type=profile.public_ws_inst_type,
            private_ws_inst_type=profile.private_ws_inst_type,
            metadata_source=profile.private_account_assets_path
            or profile.public_symbol_config_path,
            metadata_verified=True,
            status=trading_status,
            inventory_visible=eflags["inventory_visible"],
            analytics_eligible=eflags["analytics_eligible"],
            paper_shadow_eligible=eflags["paper_shadow_eligible"],
            live_execution_enabled=eflags["live_execution_enabled"],
            execution_disabled=eflags["execution_disabled"],
            trading_status=trading_status,
            trading_enabled=eflags["trading_enabled"],
            subscribe_enabled=eflags["subscribe_enabled"],
            supports_reduce_only=profile.supports_reduce_only,
            supports_long_short=profile.supports_long_short,
            supports_shorting=profile.supports_shorting,
            supports_leverage=profile.supports_leverage,
            uses_spot_public_market_data=profile.uses_spot_public_market_data,
            base_coin=str(spot_row.get("baseCoin") or "") or None,
            quote_coin=str(spot_row.get("quoteCoin") or "") or None,
            price_tick_size=_bitget_spot_tick_size_from_row(spot_row),
            quantity_step=_bitget_spot_quantity_step_from_row(spot_row),
            quantity_min=str(spot_row.get("minTradeAmount") or "") or None,
            quantity_max=str(spot_row.get("maxTradeAmount") or "") or None,
            min_notional_quote=str(spot_row.get("minTradeUSDT") or "") or None,
            price_precision=_bitget_metadata_optional_int(spot_row.get("pricePrecision")),
            quantity_precision=_bitget_metadata_optional_int(spot_row.get("quantityPrecision")),
            quote_precision=_bitget_metadata_optional_int(spot_row.get("quotePrecision")),
            symbol_type="margin",
            maintenance_margin_rate_0_1=_bitget_metadata_optional_mmr_0_1(spot_row),
            session_metadata={"schedule": "24x7", "timezone": "UTC"},
            refresh_ts_ms=rts,
            raw_metadata=spot_row,
        )


class BitgetAssetUniverseInstrument(BaseModel):
    """Governance-Sicht fuer Multi-Asset-Eligibility und Live-Blocker."""

    symbol: str
    base_coin: str | None = None
    quote_coin: str | None = None
    market_family: MarketFamily
    product_type: str | None = None
    margin_coin: str | None = None
    margin_mode: MarginAccountMode | None = None
    tick_size: str | None = None
    lot_size: str | None = None
    min_qty: str | None = None
    min_order_size: str | None = None
    min_notional: str | None = None
    max_order_size: str | None = None
    price_precision: int | None = None
    quantity_precision: int | None = None
    status: AssetUniverseStatus = "unknown"
    is_tradable: bool = False
    tradable: bool = False
    is_chart_visible: bool = False
    is_live_allowed: bool = False
    is_delisted: bool = False
    is_quarantined: bool = False
    block_reasons: list[str] = Field(default_factory=list)
    discovered_at: int | None = None
    last_verified_at: int | None = None
    fetched_at: int | None = None
    metadata_age_sec: int | None = None
    evidence_hash: str | None = None
    source: str = "runtime_catalog"
    asset_tier: int = 0
    data_quality_ok: bool = False
    liquidity_ok: bool = False
    risk_tier_assigned: bool = False
    strategy_evidence_ready: bool = False
    owner_approved: bool = False

    @field_validator(
        "symbol",
        "base_coin",
        "quote_coin",
        "product_type",
        "margin_coin",
        "tick_size",
        "lot_size",
        "min_qty",
        "min_order_size",
        "min_notional",
        "max_order_size",
        "source",
        mode="before",
    )
    @classmethod
    def _normalize_governance_text(cls, value: object, info) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None if info.field_name != "source" else "runtime_catalog"
        if info.field_name in {"symbol", "base_coin", "quote_coin", "product_type", "margin_coin"}:
            return normalized.upper()
        return normalized

    @field_validator("status", mode="before")
    @classmethod
    def _normalize_status(cls, value: object) -> object:
        if value is None:
            return "unknown"
        normalized = str(value).strip().lower()
        return normalized or "unknown"

    @field_validator("asset_tier")
    @classmethod
    def _validate_asset_tier(cls, value: int) -> int:
        if value < 0 or value > 5:
            raise ValueError("asset_tier muss im Bereich 0..5 liegen")
        return value

    @field_validator("block_reasons", mode="before")
    @classmethod
    def _normalize_block_reasons(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        out: list[str] = []
        for item in value:
            reason = str(item).strip()
            if reason and reason not in out:
                out.append(reason)
        return out

    @classmethod
    def from_catalog_entry(
        cls,
        entry: BitgetInstrumentCatalogEntry,
        *,
        status: AssetUniverseStatus = "discovered",
        asset_tier: int = 0,
        data_quality_ok: bool = False,
        liquidity_ok: bool = False,
        risk_tier_assigned: bool = False,
        strategy_evidence_ready: bool = False,
        owner_approved: bool = False,
    ) -> "BitgetAssetUniverseInstrument":
        refresh_ts = entry.refresh_ts_ms
        return cls(
            symbol=entry.symbol,
            base_coin=entry.base_coin,
            quote_coin=entry.quote_coin,
            market_family=entry.market_family,
            product_type=entry.product_type,
            margin_coin=entry.margin_coin,
            margin_mode=entry.margin_account_mode,
            tick_size=entry.price_tick_size,
            lot_size=entry.quantity_step,
            min_qty=entry.quantity_min,
            min_order_size=entry.quantity_min,
            min_notional=entry.min_notional_quote,
            max_order_size=entry.quantity_max,
            price_precision=entry.price_precision,
            quantity_precision=entry.quantity_precision,
            status=status,
            is_tradable=entry.trading_enabled,
            tradable=entry.trading_enabled,
            is_chart_visible=entry.subscribe_enabled,
            is_delisted=str(entry.status or "").lower() == "delisted",
            is_quarantined=False,
            discovered_at=refresh_ts,
            last_verified_at=refresh_ts,
            fetched_at=refresh_ts,
            metadata_age_sec=0 if refresh_ts is not None else None,
            evidence_hash=entry.canonical_instrument_id,
            source=entry.metadata_source or "runtime_catalog",
            asset_tier=asset_tier,
            data_quality_ok=data_quality_ok,
            liquidity_ok=liquidity_ok,
            risk_tier_assigned=risk_tier_assigned,
            strategy_evidence_ready=strategy_evidence_ready,
            owner_approved=owner_approved,
        )

    def evaluate_live_eligibility(self) -> tuple[bool, list[str]]:
        reasons = list(self.block_reasons)
        status = self.status
        if status == "unknown":
            reasons.append("status_unknown")
        if status in {"delisted", "suspended", "blocked", "quarantined"}:
            reasons.append(f"status_{status}")
        if self.is_delisted:
            reasons.append("is_delisted")
        if self.is_quarantined:
            reasons.append("is_quarantined")
        if self.market_family == "futures" and not self.product_type:
            reasons.append("missing_product_type_for_futures")
        if self.market_family == "futures" and not self.margin_coin:
            reasons.append("missing_margin_coin_for_futures")
        if self.price_precision is None or self.quantity_precision is None:
            reasons.append("missing_precision")
        if not self.tick_size:
            reasons.append("missing_tick_size")
        if not self.lot_size:
            reasons.append("missing_lot_size")
        if not (self.min_qty or self.min_order_size):
            reasons.append("missing_min_qty")
        if not self.min_notional:
            reasons.append("missing_min_notional")
        if not self.data_quality_ok:
            reasons.append("missing_data_quality_gate")
        if not self.liquidity_ok:
            reasons.append("missing_liquidity_gate")
        if not self.risk_tier_assigned:
            reasons.append("missing_risk_tier_gate")
        if not self.strategy_evidence_ready:
            reasons.append("missing_strategy_evidence_gate")
        if not self.owner_approved:
            reasons.append("missing_owner_approval")
        if self.asset_tier == 0:
            reasons.append("tier_0_blocked")
        if self.asset_tier == 5:
            reasons.append("tier_5_blocked")
        if self.asset_tier == 4:
            reasons.append("tier_4_shadow_only")
        if self.asset_tier == 1 and status not in {"live_candidate", "live_allowed"}:
            reasons.append("tier_1_requires_live_candidate_status")
        deduped = list(dict.fromkeys(reasons))
        live_allowed = len(deduped) == 0
        return live_allowed, deduped


def evaluate_asset_universe_live_eligibility(
    instrument: BitgetAssetUniverseInstrument,
) -> BitgetAssetUniverseInstrument:
    live_allowed, reasons = instrument.evaluate_live_eligibility()
    payload = instrument.model_dump(mode="json")
    payload["is_live_allowed"] = live_allowed
    payload["block_reasons"] = reasons
    return BitgetAssetUniverseInstrument.model_validate(payload)
