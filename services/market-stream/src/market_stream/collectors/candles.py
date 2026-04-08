from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Callable

import httpx

from market_stream.bitget_ws.subscriptions import Subscription
from market_stream.provider_diagnostics import ProviderDiagnostics
from market_stream.sinks.eventbus import AsyncRedisEventBus
from market_stream.storage.candles_repo import CandlesRepository
from shared_py.bitget import BitgetSettings
from shared_py.bitget.instruments import BitgetInstrumentCatalogEntry
from shared_py.eventbus import EventEnvelope, STREAM_CANDLE_CLOSE

if TYPE_CHECKING:
    CatalogEntryProvider = Callable[[], BitgetInstrumentCatalogEntry | None]

CANDLE_TIMEFRAMES = ("1m", "5m", "15m", "1H", "4H")
TIMEFRAME_TO_CHANNEL = {
    "1m": "candle1m",
    "5m": "candle5m",
    "15m": "candle15m",
    "1H": "candle1H",
    "4H": "candle4H",
}
CHANNEL_TO_TIMEFRAME = {value: key for key, value in TIMEFRAME_TO_CHANNEL.items()}
TIMEFRAME_TO_MS = {
    "1m": 60_000,
    "5m": 5 * 60_000,
    "15m": 15 * 60_000,
    "1H": 60 * 60_000,
    "4H": 4 * 60 * 60_000,
}


@dataclass(frozen=True)
class Candle:
    symbol: str
    timeframe: str
    start_ts_ms: int
    o: Decimal
    h: Decimal
    l: Decimal
    c: Decimal
    base_vol: Decimal
    quote_vol: Decimal
    usdt_vol: Decimal

    def as_payload(self) -> dict[str, str | int]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_ts_ms": self.start_ts_ms,
            "open": str(self.o),
            "high": str(self.h),
            "low": str(self.l),
            "close": str(self.c),
            "base_vol": str(self.base_vol),
            "quote_vol": str(self.quote_vol),
            "usdt_vol": str(self.usdt_vol),
        }


def parse_ws_candle(symbol: str, timeframe: str, arr: list[str]) -> Candle:
    return _parse_candle_row(symbol=symbol, timeframe=timeframe, arr=arr)


def parse_rest_candle(symbol: str, timeframe: str, arr: list[str | int]) -> Candle:
    normalized = [str(item) for item in arr]
    return _parse_candle_row(symbol=symbol, timeframe=timeframe, arr=normalized)


def timeframe_to_ms(timeframe: str) -> int:
    try:
        return TIMEFRAME_TO_MS[timeframe]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe}") from exc


def is_timeframe_aligned(start_ts_ms: int, timeframe: str) -> bool:
    return start_ts_ms % timeframe_to_ms(timeframe) == 0


class CandleCollector:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        candles_repo: CandlesRepository,
        event_bus: AsyncRedisEventBus,
        logger: logging.Logger | None = None,
        initial_load_limit: int = 300,
        kline_type: str = "MARKET",
        retention_days_by_timeframe: dict[str, int],
        retention_interval_sec: int = 12 * 60 * 60,
        catalog_entry_provider: "CatalogEntryProvider | None" = None,
        provider_diagnostics: ProviderDiagnostics | None = None,
        rest_429_max_retries: int = 3,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._candles_repo = candles_repo
        self._event_bus = event_bus
        self._logger = logger or logging.getLogger("market_stream.candles")
        self._initial_load_limit = min(initial_load_limit, 1000)
        self._kline_type = kline_type
        self._retention_days_by_timeframe = retention_days_by_timeframe
        self._retention_interval_sec = retention_interval_sec
        self._catalog_entry_provider = catalog_entry_provider
        self._provider_diagnostics = provider_diagnostics
        self._rest_429_max_retries = max(0, rest_429_max_retries)
        self._current_candles: dict[str, Candle] = {}
        self._last_close_emitted_start: dict[str, int] = {}
        self._initial_load_complete = False
        self._last_initial_load_ts_ms: int | None = None
        self._last_close_event_ts_ms: int | None = None
        self._last_candle_persist_ts_ms: int | None = None
        self._last_successful_candle_bar: dict[str, Any] | None = None
        self._retention_task: asyncio.Task[None] | None = None

    @property
    def initial_load_complete(self) -> bool:
        return self._initial_load_complete

    @property
    def last_initial_load_ts_ms(self) -> int | None:
        return self._last_initial_load_ts_ms

    @property
    def last_close_event_ts_ms(self) -> int | None:
        return self._last_close_event_ts_ms

    @property
    def last_candle_persist_ts_ms(self) -> int | None:
        return self._last_candle_persist_ts_ms

    def last_successful_candle_bar(self) -> dict[str, Any] | None:
        return self._last_successful_candle_bar

    def subscriptions(self) -> list[Subscription]:
        return [
            Subscription(
                inst_type=self._bitget_settings.public_ws_inst_type,
                channel=TIMEFRAME_TO_CHANNEL[timeframe],
                inst_id=self._bitget_settings.symbol,
            )
            for timeframe in CANDLE_TIMEFRAMES
        ]

    def stats_payload(self) -> dict[str, object]:
        return {
            "candle_initial_load_complete": self._initial_load_complete,
            "last_initial_load_ts_ms": self._last_initial_load_ts_ms,
            "last_candle_close_ts_ms": self._last_close_event_ts_ms,
            "last_candle_persist_ts_ms": self._last_candle_persist_ts_ms,
            "last_successful_candle_bar": self._last_successful_candle_bar,
            "tracked_timeframes": list(CANDLE_TIMEFRAMES),
            "candle_channel_map": dict(TIMEFRAME_TO_CHANNEL),
            "configured_symbol": self._bitget_settings.symbol,
            "current_open_start_ts_ms": {
                timeframe: candle.start_ts_ms
                for timeframe, candle in self._current_candles.items()
            },
        }

    async def start(self) -> None:
        await self._candles_repo.connect()
        await self._event_bus.connect()
        await self.refresh_from_rest(reason="initial-load")
        await self.run_retention_once()
        self._retention_task = asyncio.create_task(
            self._retention_loop(),
            name="market-stream-candle-retention",
        )

    async def stop(self) -> None:
        if self._retention_task is not None:
            self._retention_task.cancel()
            await asyncio.gather(self._retention_task, return_exceptions=True)
        await self._candles_repo.close()

    async def on_connected(self, *, is_reconnect: bool) -> None:
        if is_reconnect:
            await self.refresh_from_rest(reason="reconnect")

    async def handle_ws_message(self, message: dict[str, Any]) -> None:
        arg = message.get("arg")
        if not isinstance(arg, dict):
            return
        channel = arg.get("channel")
        if not isinstance(channel, str):
            return
        timeframe = CHANNEL_TO_TIMEFRAME.get(channel)
        if timeframe is None:
            return

        raw_rows = message.get("data")
        if not isinstance(raw_rows, list):
            return

        candles: list[Candle] = []
        for row in raw_rows:
            if not isinstance(row, list) or len(row) < 7:
                await self._event_bus.publish_dlq(
                    {
                        "event_type": "candle_close",
                        "symbol": self._bitget_settings.symbol,
                        "timeframe": timeframe,
                        "payload": row,
                    },
                    {
                        "stage": "validate_ws_candle_payload",
                        "error": "invalid WS candle payload",
                    },
                )
                self._logger.warning("invalid WS candle payload timeframe=%s row=%s", timeframe, row)
                continue
            try:
                candles.append(
                    parse_ws_candle(
                        symbol=self._bitget_settings.symbol,
                        timeframe=timeframe,
                        arr=[str(item) for item in row],
                    )
                )
            except (InvalidOperation, ValueError) as exc:
                await self._event_bus.publish_dlq(
                    {
                        "event_type": "candle_close",
                        "symbol": self._bitget_settings.symbol,
                        "timeframe": timeframe,
                        "payload": row,
                    },
                    {
                        "stage": "parse_ws_candle",
                        "error": str(exc),
                    },
                )
                self._logger.warning(
                    "failed to parse WS candle timeframe=%s error=%s row=%s",
                    timeframe,
                    exc,
                    row,
                )
        if candles:
            await self._ingest_candles(
                candles,
                origin="ws",
                emit_latest_closed_from_history=False,
            )

    async def refresh_from_rest(self, *, reason: str) -> None:
        self._logger.info(
            "starting candle REST sync reason=%s limit=%s",
            reason,
            self._initial_load_limit,
        )
        had_error = False
        for timeframe in CANDLE_TIMEFRAMES:
            try:
                candles = await self._load_timeframe_from_rest(timeframe=timeframe)
                await self._ingest_candles(
                    candles,
                    origin=f"rest:{reason}",
                    emit_latest_closed_from_history=True,
                )
            except ValueError as exc:
                had_error = True
                if self._provider_diagnostics is not None:
                    self._provider_diagnostics.record_protocol_error(
                        "rest_candles",
                        f"timeframe={timeframe} reason={reason} err={exc}",
                    )
                self._logger.warning(
                    "candle REST sync failed timeframe=%s reason=%s error=%s",
                    timeframe,
                    reason,
                    exc,
                )
            except httpx.HTTPStatusError as exc:
                had_error = True
                if self._provider_diagnostics is not None:
                    self._provider_diagnostics.record_protocol_error(
                        "rest_candles_http",
                        f"timeframe={timeframe} status={exc.response.status_code} reason={reason}",
                    )
                self._logger.warning(
                    "candle REST sync failed timeframe=%s reason=%s error=%s",
                    timeframe,
                    reason,
                    exc,
                )
            except Exception as exc:
                had_error = True
                if self._provider_diagnostics is not None:
                    self._provider_diagnostics.record_transport_error(
                        f"rest_candles timeframe={timeframe} reason={reason} err={type(exc).__name__}: {exc}"
                    )
                self._logger.warning(
                    "candle REST sync failed timeframe=%s reason=%s error=%s",
                    timeframe,
                    reason,
                    exc,
                )
        if reason == "initial-load":
            self._initial_load_complete = not had_error
        elif not had_error:
            self._initial_load_complete = True
        self._last_initial_load_ts_ms = int(time.time() * 1000)
        self._logger.info("finished candle REST sync reason=%s", reason)

    async def run_retention_once(self) -> None:
        now_ms = int(time.time() * 1000)
        for timeframe, retention_days in self._retention_days_by_timeframe.items():
            cutoff_ts_ms = now_ms - retention_days * 24 * 60 * 60 * 1000
            deleted_rows = await self._candles_repo.delete_older_than(
                symbol=self._bitget_settings.symbol,
                timeframe=timeframe,
                cutoff_ts_ms=cutoff_ts_ms,
            )
            if deleted_rows:
                self._logger.info(
                    "deleted %s old candles timeframe=%s cutoff_ts_ms=%s",
                    deleted_rows,
                    timeframe,
                    cutoff_ts_ms,
                )

    async def _retention_loop(self) -> None:
        while True:
            await asyncio.sleep(self._retention_interval_sec)
            await self.run_retention_once()

    async def _load_timeframe_from_rest(self, *, timeframe: str) -> list[Candle]:
        endpoint = self._bitget_settings.endpoint_profile.public_candles_path
        params = {
            "symbol": self._bitget_settings.symbol,
            "granularity": self._bitget_settings.candle_granularity(timeframe),
            "limit": str(self._initial_load_limit),
        }
        if self._bitget_settings.rest_product_type_param:
            params["productType"] = self._bitget_settings.rest_product_type_param
        if self._kline_type and self._bitget_settings.market_family == "futures":
            params["kLineType"] = self._kline_type
        self._logger.info(
            "initial load REST call endpoint=%s timeframe=%s params=%s",
            endpoint,
            timeframe,
            params,
        )
        url = f"{self._bitget_settings.effective_rest_base_url}{endpoint}"
        headers = {"Accept": "application/json"}
        max_attempts = 1 + self._rest_429_max_retries
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload: dict[str, Any] | None = None
            for attempt in range(max_attempts):
                response = await client.get(url, params=params, headers=headers)
                if response.status_code == 429 and attempt < max_attempts - 1:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.strip().isdigit():
                        wait = min(float(retry_after.strip()), 30.0)
                    else:
                        wait = min(0.5 * (2**attempt), 30.0)
                    self._logger.warning(
                        "Bitget candles REST 429 timeframe=%s attempt=%s/%s wait_s=%.2f",
                        timeframe,
                        attempt + 1,
                        max_attempts,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                raw = response.json()
                if not isinstance(raw, dict):
                    raise ValueError("Bitget candle response muss ein JSON-Objekt sein")
                payload = raw
                break
        if payload is None:
            raise ValueError("Bitget candle response fehlt nach REST-Versuchen")
        code = payload.get("code")
        if code not in (None, "00000"):
            msg = payload.get("msg") or payload.get("message") or ""
            msg_s = str(msg).strip()[:400]
            raise ValueError(
                f"Bitget oeffentliche Candles API code={code!r} msg={msg_s!r} "
                f"(Symbol {self._bitget_settings.symbol!r}, granularity={params.get('granularity')!r}) — "
                "Pruefen: BITGET_SYMBOL, BITGET_MARKET_FAMILY, Futures productType; "
                "oeffentlicher Endpoint braucht keine Account-Keys."
            )

        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("Bitget candle response data muss eine Liste sein")

        candles: list[Candle] = []
        for row in data:
            if not isinstance(row, list) or len(row) < 7:
                self._logger.warning("invalid REST candle payload timeframe=%s row=%s", timeframe, row)
                continue
            candles.append(
                parse_rest_candle(
                    symbol=self._bitget_settings.symbol,
                    timeframe=timeframe,
                    arr=row,
                )
            )
        return _dedupe_and_sort_candles(candles)

    async def _ingest_candles(
        self,
        candles: list[Candle],
        *,
        origin: str,
        emit_latest_closed_from_history: bool,
    ) -> None:
        ordered = _dedupe_and_sort_candles(candles)
        if not ordered:
            return

        valid_candles: list[Candle] = []
        for candle in ordered:
            if not is_timeframe_aligned(candle.start_ts_ms, candle.timeframe):
                self._logger.warning(
                    "unaligned candle timeframe=%s start_ts_ms=%s",
                    candle.timeframe,
                    candle.start_ts_ms,
                )
                continue
            valid_candles.append(candle)
        if not valid_candles:
            return

        await self._candles_repo.upsert_candles(valid_candles)
        last_bar = valid_candles[-1]
        self._last_candle_persist_ts_ms = int(time.time() * 1000)
        self._last_successful_candle_bar = {
            "symbol": last_bar.symbol,
            "timeframe": last_bar.timeframe,
            "start_ts_ms": last_bar.start_ts_ms,
            "origin": origin,
        }

        timeframe = valid_candles[0].timeframe
        if emit_latest_closed_from_history:
            await self._emit_latest_closed_from_history(valid_candles, origin=origin)

        for candle in valid_candles:
            current = self._current_candles.get(timeframe)
            if current is not None and candle.start_ts_ms > current.start_ts_ms:
                if not emit_latest_closed_from_history:
                    await self._emit_close_event(current, origin=origin)
            if current is None or candle.start_ts_ms >= current.start_ts_ms:
                self._current_candles[timeframe] = candle

    async def _emit_latest_closed_from_history(
        self,
        candles: list[Candle],
        *,
        origin: str,
    ) -> None:
        if len(candles) < 2:
            return
        latest_closed = candles[-2]
        await self._emit_close_event(latest_closed, origin=origin)

    async def _emit_close_event(self, candle: Candle, *, origin: str) -> None:
        last_emitted = self._last_close_emitted_start.get(candle.timeframe)
        if last_emitted == candle.start_ts_ms:
            return

        close_ts_ms = candle.start_ts_ms + timeframe_to_ms(candle.timeframe)
        try:
            envelope = EventEnvelope(
                event_type="candle_close",
                symbol=candle.symbol,
                instrument=self._event_instrument(),
                timeframe=candle.timeframe,
                exchange_ts_ms=close_ts_ms,
                dedupe_key=f"{candle.symbol}:{candle.timeframe}:{candle.start_ts_ms}",
                payload={
                    **candle.as_payload(),
                    "origin": origin,
                },
                trace={
                    "source": "market_stream.candles",
                    "product_type": self._bitget_settings.product_type,
                    "market_family": self._bitget_settings.market_family,
                },
            )
            message_id = await self._event_bus.publish(STREAM_CANDLE_CLOSE, envelope)
        except Exception as exc:
            await self._event_bus.publish_dlq(
                {
                    "event_type": "candle_close",
                    "symbol": candle.symbol,
                    "timeframe": candle.timeframe,
                    "exchange_ts_ms": close_ts_ms,
                    "payload": {
                        **candle.as_payload(),
                        "origin": origin,
                    },
                },
                {
                    "stage": "publish_candle_close",
                    "error": str(exc),
                },
            )
            self._logger.warning(
                "failed to publish events:candle_close timeframe=%s start_ts_ms=%s error=%s",
                candle.timeframe,
                candle.start_ts_ms,
                exc,
            )
            return
        if message_id is not None:
            self._last_close_emitted_start[candle.timeframe] = candle.start_ts_ms
            self._last_close_event_ts_ms = envelope.ingest_ts_ms
            if message_id != "deduped":
                self._logger.info(
                    "published events:candle_close timeframe=%s start_ts_ms=%s message_id=%s",
                    candle.timeframe,
                    candle.start_ts_ms,
                    message_id,
                )

    def _event_instrument(self):
        if self._catalog_entry_provider is not None:
            entry = self._catalog_entry_provider()
            if entry is not None:
                return entry.identity()
        return self._bitget_settings.instrument_identity()


def _parse_candle_row(*, symbol: str, timeframe: str, arr: list[str]) -> Candle:
    if len(arr) < 7:
        raise ValueError("candle payload needs at least 7 values")
    start_ts = int(arr[0])
    usdt_vol = arr[7] if len(arr) >= 8 else arr[6]
    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        start_ts_ms=start_ts,
        o=Decimal(arr[1]),
        h=Decimal(arr[2]),
        l=Decimal(arr[3]),
        c=Decimal(arr[4]),
        base_vol=Decimal(arr[5]),
        quote_vol=Decimal(arr[6]),
        usdt_vol=Decimal(usdt_vol),
    )


def _dedupe_and_sort_candles(candles: list[Candle]) -> list[Candle]:
    deduped: dict[tuple[str, str, int], Candle] = {}
    for candle in candles:
        deduped[(candle.symbol, candle.timeframe, candle.start_ts_ms)] = candle
    return sorted(deduped.values(), key=lambda candle: candle.start_ts_ms)
