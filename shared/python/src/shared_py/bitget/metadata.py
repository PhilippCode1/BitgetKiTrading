from __future__ import annotations

import time
from decimal import Decimal, ROUND_FLOOR
from typing import Any, Literal

from pydantic import BaseModel, Field

from shared_py.bitget.catalog import (
    BitgetInstrumentCatalog,
    InstrumentCatalogUnavailableError,
    UnknownInstrumentError,
)
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry

MetadataHealthStatus = Literal["ok", "degraded", "unavailable"]


def _dec(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _round_down_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    units = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return units * step


class InstrumentSessionState(BaseModel):
    trade_allowed_now: bool
    subscribe_allowed_now: bool
    open_new_positions_allowed_now: bool
    maintenance_active: bool = False
    delivery_window_active: bool = False
    reasons: list[str] = Field(default_factory=list)


class BitgetInstrumentResolvedMetadata(BaseModel):
    snapshot_id: str
    entry: BitgetInstrumentCatalogEntry
    session_state: InstrumentSessionState
    health_status: MetadataHealthStatus
    health_reasons: list[str] = Field(default_factory=list)

    @property
    def canonical_instrument_id(self) -> str:
        return self.entry.canonical_instrument_id or self.entry.instrument_key

    @property
    def trading_enabled_now(self) -> bool:
        return self.entry.trading_enabled and self.session_state.trade_allowed_now

    @property
    def subscribe_enabled_now(self) -> bool:
        return self.entry.subscribe_enabled and self.session_state.subscribe_allowed_now


class OrderPreflightResult(BaseModel):
    metadata: BitgetInstrumentResolvedMetadata
    normalized_price: str | None = None
    normalized_size: str
    computed_notional_quote: str | None = None
    reasons: list[str] = Field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.reasons


class BitgetInstrumentMetadataService:
    def __init__(self, catalog: BitgetInstrumentCatalog) -> None:
        self._catalog = catalog

    def resolve_metadata(
        self,
        *,
        symbol: str,
        market_family: str | None = None,
        product_type: str | None = None,
        margin_account_mode: str | None = None,
        refresh_if_missing: bool = False,
    ) -> BitgetInstrumentResolvedMetadata:
        snapshot = self._catalog.require_catalog(refresh_if_missing=refresh_if_missing)
        entry = self._catalog.resolve(
            symbol=symbol,
            market_family=market_family,
            product_type=product_type,
            margin_account_mode=margin_account_mode,
            refresh_if_missing=refresh_if_missing,
        )
        health_reasons = self._entry_health_reasons(entry)
        health_status: MetadataHealthStatus = "ok" if not health_reasons else "degraded"
        return BitgetInstrumentResolvedMetadata(
            snapshot_id=snapshot.snapshot_id,
            entry=entry,
            session_state=self._session_state(entry),
            health_status=health_status,
            health_reasons=health_reasons,
        )

    def resolve_for_trading(
        self,
        **kwargs: Any,
    ) -> BitgetInstrumentResolvedMetadata:
        metadata = self.resolve_metadata(**kwargs)
        if not metadata.trading_enabled_now:
            raise UnknownInstrumentError(
                f"instrument_not_tradeable canonical_id={metadata.canonical_instrument_id}"
            )
        return metadata

    def resolve_for_subscription(
        self,
        **kwargs: Any,
    ) -> BitgetInstrumentResolvedMetadata:
        metadata = self.resolve_metadata(**kwargs)
        if not metadata.subscribe_enabled_now:
            raise UnknownInstrumentError(
                f"instrument_not_subscribable canonical_id={metadata.canonical_instrument_id}"
            )
        return metadata

    def preflight_order(
        self,
        *,
        metadata: BitgetInstrumentResolvedMetadata,
        side: str,
        order_type: str,
        size: str,
        price: str | None,
        reduce_only: bool,
        quote_size_order: bool,
        max_metadata_age_sec: int | None = None,
        now_ms: int | None = None,
        account_margin_coin: str | None = None,
    ) -> OrderPreflightResult:
        reasons = list(metadata.health_reasons)
        if not metadata.trading_enabled_now:
            reasons.append("instrument_session_not_tradeable")
        if not reduce_only and not metadata.session_state.open_new_positions_allowed_now:
            reasons.append("instrument_open_session_restricted")
        if reduce_only and not metadata.entry.supports_reduce_only:
            reasons.append("instrument_does_not_support_reduce_only")

        now = int(now_ms if now_ms is not None else int(time.time() * 1000))
        if (
            max_metadata_age_sec is not None
            and max_metadata_age_sec > 0
            and metadata.entry.refresh_ts_ms is not None
        ):
            try:
                age_sec = (now - int(metadata.entry.refresh_ts_ms)) / 1000.0
            except (TypeError, ValueError):
                age_sec = None
            if age_sec is not None and age_sec > float(max_metadata_age_sec):
                reasons.append("catalog_metadata_stale")

        acct_mc = str(account_margin_coin or "").strip().upper()
        if acct_mc and metadata.entry.supported_margin_coins:
            allowed = {
                str(x).strip().upper()
                for x in metadata.entry.supported_margin_coins
                if str(x).strip()
            }
            if allowed and acct_mc not in allowed:
                reasons.append("margin_coin_not_instrument_supported_list")

        raw_size = _dec(size)
        if raw_size is None or raw_size <= 0:
            reasons.append("order_size_invalid")
            raw_size = Decimal("0")
        raw_price = _dec(price) if price not in (None, "") else None
        normalized_price: Decimal | None = raw_price
        normalized_size = raw_size

        if raw_price is not None and metadata.entry.price_tick_size:
            tick = _dec(metadata.entry.price_tick_size)
            if tick is not None and tick > 0:
                normalized_price = _round_down_to_step(raw_price, tick)
                if normalized_price != raw_price:
                    reasons.append("price_rounded_to_tick")

        if quote_size_order:
            quote_precision = metadata.entry.quote_precision
            if quote_precision is not None:
                step = Decimal("1") / (Decimal("10") ** quote_precision)
                rounded = _round_down_to_step(raw_size, step)
                if rounded != raw_size:
                    reasons.append("quote_size_rounded_to_precision")
                normalized_size = rounded
        else:
            step = _dec(metadata.entry.quantity_step)
            if step is not None and step > 0:
                rounded = _round_down_to_step(raw_size, step)
                if rounded != raw_size:
                    reasons.append("size_rounded_to_step")
                normalized_size = rounded

        quantity_min = _dec(metadata.entry.quantity_min)
        if quantity_min is not None and not quote_size_order and normalized_size < quantity_min:
            reasons.append("order_size_below_minimum")
        quantity_max = _dec(
            metadata.entry.market_order_quantity_max
            if order_type == "market"
            else metadata.entry.quantity_max
        )
        if quantity_max is not None and normalized_size > quantity_max:
            reasons.append("order_size_above_maximum")

        notional_quote = None
        if quote_size_order:
            notional_quote = normalized_size
        elif normalized_price is not None:
            notional_quote = normalized_price * normalized_size
        min_notional = _dec(metadata.entry.min_notional_quote)
        if min_notional is not None and notional_quote is not None and notional_quote < min_notional:
            reasons.append("order_notional_below_minimum")

        return OrderPreflightResult(
            metadata=metadata,
            normalized_price=(format(normalized_price, "f") if normalized_price is not None else None),
            normalized_size=format(normalized_size, "f"),
            computed_notional_quote=(format(notional_quote, "f") if notional_quote is not None else None),
            reasons=list(dict.fromkeys(reasons)),
        )

    def exit_validation_context(
        self,
        *,
        metadata: BitgetInstrumentResolvedMetadata,
        entry_price: Decimal,
    ) -> dict[str, Any]:
        tick = _dec(metadata.entry.price_tick_size)
        tick_bps = None
        if tick is not None and entry_price > 0:
            tick_bps = (tick / entry_price) * Decimal("10000")
        return {
            "market_family": metadata.entry.market_family,
            "price_tick_size": tick,
            "tick_size_bps": tick_bps,
            "quantity_step": _dec(metadata.entry.quantity_step),
            "quantity_min": _dec(metadata.entry.quantity_min),
            "quantity_max": _dec(metadata.entry.quantity_max),
            "trading_status": metadata.entry.trading_status,
            "session_trade_allowed": metadata.session_state.trade_allowed_now,
            "session_open_new_positions_allowed": metadata.session_state.open_new_positions_allowed_now,
            "catalog_snapshot_id": metadata.snapshot_id,
        }

    def health_payload(self) -> dict[str, Any]:
        try:
            snapshot = self._catalog.require_catalog(refresh_if_missing=False)
        except InstrumentCatalogUnavailableError:
            return {"status": "unavailable", "reason": "catalog_missing"}
        stale = self._catalog.health_payload().get("stale", False)
        degraded_ids = [
            entry.canonical_instrument_id or entry.instrument_key
            for entry in snapshot.entries
            if self._entry_health_reasons(entry)
        ]
        status: MetadataHealthStatus = "degraded" if stale or degraded_ids else "ok"
        return {
            "status": status,
            "snapshot_id": snapshot.snapshot_id,
            "counts_by_family": dict(snapshot.counts_by_family),
            "warnings": list(snapshot.warnings),
            "errors": list(snapshot.errors),
            "stale": bool(stale),
            "degraded_entry_count": len(degraded_ids),
            "degraded_entries_sample": degraded_ids[:10],
        }

    def _entry_health_reasons(self, entry: BitgetInstrumentCatalogEntry) -> list[str]:
        reasons: list[str] = []
        if not entry.price_tick_size:
            reasons.append("metadata_missing_price_tick")
        if not entry.quantity_step and entry.market_family != "spot":
            reasons.append("metadata_missing_quantity_step")
        if not entry.quantity_min:
            reasons.append("metadata_missing_quantity_min")
        if entry.market_family in {"margin", "futures"} and entry.leverage_max is None:
            reasons.append("metadata_missing_leverage_cap")
        if entry.market_family == "futures" and entry.funding_interval_hours is None:
            reasons.append("metadata_missing_funding_interval")
        qmin = _dec(entry.quantity_min)
        qmax = _dec(entry.quantity_max)
        if qmin is not None and qmax is not None and qmax < qmin:
            reasons.append("metadata_quantity_range_invalid")
        if (
            entry.leverage_min is not None
            and entry.leverage_max is not None
            and entry.leverage_max < entry.leverage_min
        ):
            reasons.append("metadata_leverage_range_invalid")
        return reasons

    def _session_state(self, entry: BitgetInstrumentCatalogEntry) -> InstrumentSessionState:
        meta = dict(entry.session_metadata or {})
        now_ms = int(time.time() * 1000)
        reasons: list[str] = []
        maintenance_active = False
        delivery_window_active = False
        trade_allowed_now = entry.trading_enabled
        subscribe_allowed_now = entry.subscribe_enabled
        open_new_positions_allowed_now = entry.trading_enabled

        status = str(entry.trading_status or "").strip().lower()
        if status in {"maintain", "off", "restrictedapi"}:
            trade_allowed_now = False
            open_new_positions_allowed_now = False
            if status == "maintain":
                maintenance_active = True
            reasons.append(f"trading_status_{status}")
        if status == "limit_open":
            open_new_positions_allowed_now = False
            reasons.append("trading_status_limit_open")

        maintain_time = meta.get("maintain_time")
        if isinstance(maintain_time, int) and maintain_time > 0 and now_ms >= maintain_time:
            maintenance_active = True
            trade_allowed_now = False
            open_new_positions_allowed_now = False
            reasons.append("maintenance_window_active")

        delivery_start = meta.get("delivery_start_time")
        delivery_time = meta.get("delivery_time")
        if isinstance(delivery_start, int) and delivery_start > 0 and now_ms >= delivery_start:
            delivery_window_active = True
            open_new_positions_allowed_now = False
            reasons.append("delivery_window_active")
        if isinstance(delivery_time, int) and delivery_time > 0 and now_ms >= delivery_time:
            trade_allowed_now = False
            subscribe_allowed_now = False
            open_new_positions_allowed_now = False
            delivery_window_active = True
            reasons.append("delivery_complete")

        return InstrumentSessionState(
            trade_allowed_now=trade_allowed_now,
            subscribe_allowed_now=subscribe_allowed_now,
            open_new_positions_allowed_now=open_new_positions_allowed_now,
            maintenance_active=maintenance_active,
            delivery_window_active=delivery_window_active,
            reasons=reasons,
        )
