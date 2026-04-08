from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, fields
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import httpx
from shared_py.bitget import BitgetSettings
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry
from shared_py.eventbus import STREAM_FUNDING_UPDATE, STREAM_MARKET_TICK, EventEnvelope

from market_stream.bitget_ws.subscriptions import Subscription
from market_stream.provider_diagnostics import ProviderDiagnostics
from market_stream.sinks.eventbus import AsyncRedisEventBus
from market_stream.storage.ticker_repo import TickerRepository

if TYPE_CHECKING:
    CatalogEntryProvider = Callable[[], BitgetInstrumentCatalogEntry | None]


@dataclass(frozen=True)
class TickerSnapshot:
    symbol: str
    ts_ms: int
    source: str
    last_pr: Decimal | None = None
    bid_pr: Decimal | None = None
    ask_pr: Decimal | None = None
    bid_sz: Decimal | None = None
    ask_sz: Decimal | None = None
    mark_price: Decimal | None = None
    index_price: Decimal | None = None
    funding_rate: Decimal | None = None
    next_funding_time_ms: int | None = None
    holding_amount: Decimal | None = None
    base_volume: Decimal | None = None
    quote_volume: Decimal | None = None
    funding_rate_interval: str | None = None
    funding_next_update_ms: int | None = None
    funding_min_rate: Decimal | None = None
    funding_max_rate: Decimal | None = None
    ingest_ts_ms: int = 0

    def as_payload(self) -> dict[str, str | int | None]:
        return {
            "symbol": self.symbol,
            "source": self.source,
            "ts_ms": self.ts_ms,
            "last_pr": _decimal_str(self.last_pr),
            "bid_pr": _decimal_str(self.bid_pr),
            "ask_pr": _decimal_str(self.ask_pr),
            "bid_sz": _decimal_str(self.bid_sz),
            "ask_sz": _decimal_str(self.ask_sz),
            "mark_price": _decimal_str(self.mark_price),
            "index_price": _decimal_str(self.index_price),
            "funding_rate": _decimal_str(self.funding_rate),
            "next_funding_time_ms": self.next_funding_time_ms,
            "holding_amount": _decimal_str(self.holding_amount),
            "base_volume": _decimal_str(self.base_volume),
            "quote_volume": _decimal_str(self.quote_volume),
            "funding_rate_interval": self.funding_rate_interval,
            "funding_next_update_ms": self.funding_next_update_ms,
            "funding_min_rate": _decimal_str(self.funding_min_rate),
            "funding_max_rate": _decimal_str(self.funding_max_rate),
        }


class TickerCollector:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        ticker_repo: TickerRepository,
        event_bus: AsyncRedisEventBus,
        oi_snapshot_interval_sec: int,
        funding_snapshot_interval_sec: int,
        symbol_price_snapshot_interval_sec: int,
        logger: logging.Logger | None = None,
        catalog_entry_provider: "CatalogEntryProvider | None" = None,
        provider_diagnostics: ProviderDiagnostics | None = None,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._ticker_repo = ticker_repo
        self._event_bus = event_bus
        self._logger = logger or logging.getLogger("market_stream.ticker")
        self._oi_snapshot_interval_sec = oi_snapshot_interval_sec
        self._funding_snapshot_interval_sec = funding_snapshot_interval_sec
        self._symbol_price_snapshot_interval_sec = symbol_price_snapshot_interval_sec
        self._catalog_entry_provider = catalog_entry_provider
        self._provider_diagnostics = provider_diagnostics
        self._latest_fields: dict[str, object] = {}
        self._http_client: httpx.AsyncClient | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._persisted_rows = 0
        self._last_ticker_ts_ms: int | None = None
        self._last_rest_snapshot_ts_ms: int | None = None
        self._published_market_tick_events = 0
        self._published_funding_update_events = 0

    def _catalog_entry(self) -> BitgetInstrumentCatalogEntry | None:
        if self._catalog_entry_provider is None:
            return None
        return self._catalog_entry_provider()

    def _effective_supports_open_interest(self) -> bool:
        profile = self._bitget_settings.endpoint_profile
        if not profile.public_open_interest_path or not profile.supports_open_interest:
            return False
        entry = self._catalog_entry()
        if entry is not None and not entry.supports_open_interest:
            return False
        return True

    def _effective_supports_funding(self) -> bool:
        profile = self._bitget_settings.endpoint_profile
        if not profile.public_funding_path or not profile.supports_funding:
            return False
        entry = self._catalog_entry()
        if entry is not None and not entry.supports_funding:
            return False
        return True

    def _ws_derivative_field_policy(self) -> tuple[bool, bool]:
        fam = self._bitget_settings.market_family
        if fam != "futures":
            return False, False
        entry = self._catalog_entry()
        sf = (
            entry.supports_funding
            if entry is not None
            else self._bitget_settings.endpoint_profile.supports_funding
        )
        soi = (
            entry.supports_open_interest
            if entry is not None
            else self._bitget_settings.endpoint_profile.supports_open_interest
        )
        return bool(sf), bool(soi)

    def subscriptions(self) -> list[Subscription]:
        return [
            Subscription(
                inst_type=self._bitget_settings.public_ws_inst_type,
                channel="ticker",
                inst_id=self._bitget_settings.symbol,
            )
        ]

    def stats_payload(self) -> dict[str, object]:
        return {
            "last_ticker_ts_ms": self._last_ticker_ts_ms,
            "last_ws_ticker_ts_ms": self._last_ticker_ts_ms,
            "last_rest_snapshot_ts_ms": self._last_rest_snapshot_ts_ms,
            "last_quote_ts_ms": self.last_quote_ts_ms(),
            "persisted_ticker_rows": self._persisted_rows,
            "published_market_tick_events": self._published_market_tick_events,
            "published_funding_update_events": self._published_funding_update_events,
        }

    def last_quote_ts_ms(self) -> int | None:
        """Max aus WS-Ticker und letztem REST-Snapshot (OI/Funding/Preis)."""
        ws_ts = self._last_ticker_ts_ms
        rest_ts = self._last_rest_snapshot_ts_ms
        candidates = [ts for ts in (ws_ts, rest_ts) if ts]
        return max(candidates) if candidates else None

    def last_ws_ticker_ts_ms(self) -> int | None:
        return self._last_ticker_ts_ms

    def last_rest_snapshot_ts_ms(self) -> int | None:
        return self._last_rest_snapshot_ts_ms

    async def start(self) -> None:
        await self._ticker_repo.connect()
        await self._event_bus.connect()
        self._http_client = httpx.AsyncClient(timeout=10.0)
        await self.refresh_rest_snapshots(reason="initial-load")
        self._tasks = []
        if self._effective_supports_open_interest():
            self._tasks.append(
                asyncio.create_task(
                    self._periodic_loop(
                        interval_sec=self._oi_snapshot_interval_sec,
                        refresh=self._refresh_open_interest,
                        name="market-stream-oi-snapshot",
                    )
                )
            )
        if self._effective_supports_funding():
            self._tasks.append(
                asyncio.create_task(
                    self._periodic_loop(
                        interval_sec=self._funding_snapshot_interval_sec,
                        refresh=self._refresh_funding_details,
                        name="market-stream-funding-snapshot",
                    )
                )
            )
        self._tasks.append(
            asyncio.create_task(
                self._periodic_loop(
                    interval_sec=self._symbol_price_snapshot_interval_sec,
                    refresh=self._refresh_symbol_price,
                    name="market-stream-symbol-price-snapshot",
                )
            )
        )

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        await self._ticker_repo.close()

    async def on_connected(self, *, is_reconnect: bool) -> None:
        if is_reconnect:
            await self.refresh_rest_snapshots(reason="reconnect")

    async def handle_ws_message(self, message: dict[str, Any]) -> None:
        arg = message.get("arg")
        if not isinstance(arg, dict) or arg.get("channel") != "ticker":
            return
        data = message.get("data")
        if not isinstance(data, list):
            return

        snapshots: list[TickerSnapshot] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                ts_ms, updates = _parse_ws_ticker_payload(item)
                sf, soi = self._ws_derivative_field_policy()
                updates = _filter_ws_ticker_updates(
                    updates,
                    self._bitget_settings.market_family,
                    supports_funding=sf,
                    supports_open_interest=soi,
                )
            except (InvalidOperation, ValueError) as exc:
                await self._event_bus.publish_dlq(
                    {
                        "event_type": "market_tick",
                        "symbol": self._bitget_settings.symbol,
                        "payload": item,
                    },
                    {
                        "stage": "parse_ws_ticker_payload",
                        "error": str(exc),
                    },
                )
                self._logger.warning("failed to parse ticker payload error=%s item=%s", exc, item)
                continue
            snapshots.append(
                self._build_snapshot(
                    source="bitget_ws_ticker",
                    ts_ms=ts_ms,
                    updates=updates,
                )
            )
        inserted = await self._ticker_repo.upsert_snapshots(snapshots)
        self._persisted_rows += inserted
        if snapshots:
            self._last_ticker_ts_ms = snapshots[-1].ts_ms
        for snapshot in snapshots:
            await self._publish_market_tick(snapshot, origin="ws")
            if snapshot.funding_rate is not None:
                await self._publish_funding_update(snapshot, origin="ws")

    async def refresh_rest_snapshots(self, *, reason: str) -> None:
        self._logger.info("starting ticker REST snapshot refresh reason=%s", reason)
        refreshers: list[tuple[str, Callable[[], Awaitable[None]]]] = []
        if self._effective_supports_open_interest():
            refreshers.append(("open-interest", self._refresh_open_interest))
        if self._effective_supports_funding():
            refreshers.append(("funding", self._refresh_funding_details))
        refreshers.append(("symbol-price", self._refresh_symbol_price))
        for name, refresh in refreshers:
            try:
                await refresh()
            except Exception as exc:
                self._logger.warning(
                    "ticker REST snapshot failed reason=%s name=%s error=%s",
                    reason,
                    name,
                    exc,
                )
        self._logger.info("finished ticker REST snapshot refresh reason=%s", reason)

    async def _periodic_loop(
        self,
        *,
        interval_sec: int,
        refresh: Callable[[], Awaitable[None]],
        name: str,
    ) -> None:
        while True:
            await asyncio.sleep(interval_sec)
            try:
                await refresh()
            except Exception as exc:
                self._logger.warning("%s failed: %s", name, exc)

    async def _refresh_open_interest(self) -> None:
        if not self._effective_supports_open_interest():
            return
        endpoint = self._bitget_settings.endpoint_profile.public_open_interest_path
        if not endpoint:
            return
        payload = await self._request_json(endpoint)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ValueError("open-interest data muss ein Objekt sein")
        open_interest_list = data.get("openInterestList")
        if not isinstance(open_interest_list, list) or not open_interest_list:
            raise ValueError("openInterestList fehlt")
        first = open_interest_list[0]
        if not isinstance(first, dict):
            raise ValueError("open-interest entry muss ein Objekt sein")
        snapshot = self._build_snapshot(
            source="bitget_rest_open_interest",
            ts_ms=_to_int(data.get("ts")) or _to_int(payload.get("requestTime")) or _now_ms(),
            updates={
                "holding_amount": _to_decimal(first.get("size")),
            },
        )
        self._persisted_rows += await self._ticker_repo.upsert_snapshots([snapshot])
        self._last_rest_snapshot_ts_ms = snapshot.ts_ms
        await self._publish_market_tick(snapshot, origin="rest")

    async def _refresh_funding_details(self) -> None:
        if not self._effective_supports_funding():
            return
        endpoint = self._bitget_settings.endpoint_profile.public_funding_path
        if not endpoint:
            return
        payload = await self._request_json(endpoint)
        item = _require_first_object(payload.get("data"))
        snapshot = self._build_snapshot(
            source="bitget_rest_funding",
            ts_ms=_to_int(payload.get("requestTime")) or _now_ms(),
            updates={
                "funding_rate": _to_decimal(item.get("fundingRate")),
                "funding_rate_interval": _to_string(item.get("fundingRateInterval")),
                "funding_next_update_ms": _to_int(item.get("nextUpdate")),
                "funding_min_rate": _to_decimal(item.get("minFundingRate")),
                "funding_max_rate": _to_decimal(item.get("maxFundingRate")),
            },
        )
        self._persisted_rows += await self._ticker_repo.upsert_snapshots([snapshot])
        self._last_rest_snapshot_ts_ms = snapshot.ts_ms
        await self._publish_funding_update(snapshot, origin="rest")

    async def _refresh_symbol_price(self) -> None:
        payload = await self._request_json(
            self._bitget_settings.endpoint_profile.public_ticker_path
        )
        item = _require_first_object(payload.get("data"))
        ts_ms = _to_int(item.get("ts")) or _to_int(payload.get("requestTime")) or _now_ms()
        updates = {
            "last_pr": _to_decimal(item.get("price") or item.get("lastPr")),
            "bid_pr": _to_decimal(item.get("bidPr")),
            "ask_pr": _to_decimal(item.get("askPr")),
            "base_volume": _to_decimal(item.get("baseVolume")),
            "quote_volume": _to_decimal(item.get("quoteVolume")),
        }
        if self._bitget_settings.market_family == "futures":
            updates["mark_price"] = _to_decimal(item.get("markPrice"))
            updates["index_price"] = _to_decimal(item.get("indexPrice"))
        snapshot = self._build_snapshot(
            source="bitget_rest_symbol_price",
            ts_ms=ts_ms,
            updates=updates,
        )
        self._persisted_rows += await self._ticker_repo.upsert_snapshots([snapshot])
        self._last_rest_snapshot_ts_ms = snapshot.ts_ms
        await self._publish_market_tick(snapshot, origin="rest")

    async def _publish_market_tick(self, snapshot: TickerSnapshot, *, origin: str) -> None:
        try:
            envelope = EventEnvelope(
                event_type="market_tick",
                symbol=snapshot.symbol,
                instrument=self._event_instrument(),
                exchange_ts_ms=snapshot.ts_ms,
                dedupe_key=f"market_tick:{snapshot.symbol}:{snapshot.ts_ms}:{snapshot.source}",
                payload={
                    **snapshot.as_payload(),
                    "origin": origin,
                },
                trace={
                    "source": "market_stream.ticker",
                    "snapshot_source": snapshot.source,
                    "market_family": self._bitget_settings.market_family,
                },
            )
            message_id = await self._event_bus.publish(STREAM_MARKET_TICK, envelope)
        except Exception as exc:
            await self._event_bus.publish_dlq(
                {
                    "event_type": "market_tick",
                    "symbol": snapshot.symbol,
                    "exchange_ts_ms": snapshot.ts_ms,
                    "payload": snapshot.as_payload(),
                },
                {
                    "stage": "publish_market_tick",
                    "error": str(exc),
                    "origin": origin,
                },
            )
            self._logger.warning("failed to publish events:market_tick error=%s", exc)
            return
        if message_id not in (None, "deduped"):
            self._published_market_tick_events += 1
            self._logger.info(
                "published events:market_tick symbol=%s ts_ms=%s message_id=%s",
                snapshot.symbol,
                snapshot.ts_ms,
                message_id,
            )

    async def _publish_funding_update(self, snapshot: TickerSnapshot, *, origin: str) -> None:
        try:
            envelope = EventEnvelope(
                event_type="funding_update",
                symbol=snapshot.symbol,
                instrument=self._event_instrument(),
                exchange_ts_ms=snapshot.ts_ms,
                dedupe_key=(
                    f"funding_update:{snapshot.symbol}:{snapshot.ts_ms}:"
                    f"{snapshot.funding_rate}:{snapshot.source}"
                ),
                payload={
                    **snapshot.as_payload(),
                    "origin": origin,
                },
                trace={
                    "source": "market_stream.ticker",
                    "snapshot_source": snapshot.source,
                    "market_family": self._bitget_settings.market_family,
                },
            )
            message_id = await self._event_bus.publish(STREAM_FUNDING_UPDATE, envelope)
        except Exception as exc:
            await self._event_bus.publish_dlq(
                {
                    "event_type": "funding_update",
                    "symbol": snapshot.symbol,
                    "exchange_ts_ms": snapshot.ts_ms,
                    "payload": snapshot.as_payload(),
                },
                {
                    "stage": "publish_funding_update",
                    "error": str(exc),
                    "origin": origin,
                },
            )
            self._logger.warning("failed to publish events:funding_update error=%s", exc)
            return
        if message_id not in (None, "deduped"):
            self._published_funding_update_events += 1
            self._logger.info(
                "published events:funding_update symbol=%s ts_ms=%s message_id=%s",
                snapshot.symbol,
                snapshot.ts_ms,
                message_id,
            )

    async def _request_json(self, endpoint: str) -> dict[str, Any]:
        if self._http_client is None:
            raise RuntimeError("ticker HTTP client not started")
        try:
            response = await self._http_client.get(
                f"{self._bitget_settings.effective_rest_base_url}{endpoint}",
                params={
                    "symbol": self._bitget_settings.symbol,
                    **(
                        {"productType": self._bitget_settings.rest_product_type_param}
                        if self._bitget_settings.rest_product_type_param
                        else {}
                    ),
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if self._provider_diagnostics is not None:
                self._provider_diagnostics.record_protocol_error(
                    "rest_ticker_http",
                    f"status={exc.response.status_code} endpoint={endpoint}",
                )
            raise
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Bitget ticker REST response muss ein JSON-Objekt sein")
        if payload.get("code") not in (None, "00000"):
            if self._provider_diagnostics is not None:
                self._provider_diagnostics.record_protocol_error(
                    "rest_ticker_api",
                    f"code={payload.get('code')!r} endpoint={endpoint}",
                )
            raise ValueError(f"Bitget ticker response code not ok: {payload.get('code')}")
        return payload

    def _build_snapshot(
        self,
        *,
        source: str,
        ts_ms: int,
        updates: dict[str, object],
    ) -> TickerSnapshot:
        normalized_updates = {key: value for key, value in updates.items() if value is not None}
        self._latest_fields.update(normalized_updates)
        snapshot_data = {
            "symbol": self._bitget_settings.symbol,
            "ts_ms": ts_ms,
            "source": source,
            "ingest_ts_ms": _now_ms(),
        }
        for field_info in fields(TickerSnapshot):
            if field_info.name in snapshot_data:
                continue
            snapshot_data[field_info.name] = self._latest_fields.get(field_info.name)
        return TickerSnapshot(**snapshot_data)

    def _event_instrument(self):
        if self._catalog_entry_provider is not None:
            entry = self._catalog_entry_provider()
            if entry is not None:
                return entry.identity()
        return self._bitget_settings.instrument_identity()


def _filter_ws_ticker_updates(
    updates: dict[str, object],
    market_family: str,
    *,
    supports_funding: bool,
    supports_open_interest: bool,
) -> dict[str, object]:
    out = dict(updates)
    fam = str(market_family).lower()
    if fam != "futures":
        for key in (
            "mark_price",
            "index_price",
            "funding_rate",
            "next_funding_time_ms",
            "holding_amount",
        ):
            out.pop(key, None)
    else:
        if not supports_funding:
            out.pop("funding_rate", None)
            out.pop("next_funding_time_ms", None)
        if not supports_open_interest:
            out.pop("holding_amount", None)
    return out


def _parse_ws_ticker_payload(item: dict[str, Any]) -> tuple[int, dict[str, object]]:
    ts_ms = _to_int(item.get("ts")) or _now_ms()
    return ts_ms, {
        "last_pr": _to_decimal(item.get("lastPr")),
        "bid_pr": _to_decimal(item.get("bidPr")),
        "ask_pr": _to_decimal(item.get("askPr")),
        "bid_sz": _to_decimal(item.get("bidSz")),
        "ask_sz": _to_decimal(item.get("askSz")),
        "mark_price": _to_decimal(item.get("markPrice")),
        "index_price": _to_decimal(item.get("indexPrice")),
        "funding_rate": _to_decimal(item.get("fundingRate")),
        "next_funding_time_ms": _to_int(item.get("nextFundingTime")),
        "holding_amount": _to_decimal(item.get("holdingAmount")),
        "base_volume": _to_decimal(item.get("baseVolume")),
        "quote_volume": _to_decimal(item.get("quoteVolume")),
    }


def _require_first_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, list) or not value:
        raise ValueError("response data muss eine nicht-leere Liste sein")
    item = value[0]
    if not isinstance(item, dict):
        raise ValueError("list entry muss ein Objekt sein")
    return item


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _to_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value.strip())
    return int(str(value))


def _to_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _now_ms() -> int:
    return int(time.time() * 1000)
