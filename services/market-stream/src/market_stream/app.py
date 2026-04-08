from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, ClassVar, Literal

from config.settings import BaseServiceSettings
from fastapi import FastAPI
from pydantic import Field, field_validator, model_validator
from pydantic_settings import SettingsConfigDict
from shared_py.bitget import (
    BitgetInstrumentCatalog,
    BitgetInstrumentMetadataService,
    BitgetSettings,
)
from shared_py.observability import (
    check_postgres,
    check_redis_url,
    instrument_fastapi,
    merge_ready_details,
    touch_worker_heartbeat,
    wait_for_datastores,
)

from market_stream.bitget_ws.client import BitgetPublicWsClient, ClientRuntimeStats
from market_stream.bitget_ws.rate_limiter import RateLimiter
from market_stream.collectors.candles import TIMEFRAME_TO_CHANNEL, CandleCollector
from market_stream.collectors.orderbook import OrderbookCollector
from market_stream.collectors.ticker import TickerCollector
from market_stream.collectors.trades import TradesCollector
from market_stream.feed_health import (
    compute_quote_age_ms,
    gapfill_triggers_orderbook_resync,
    publish_market_feed_health,
)
from market_stream.gapfill.rest_gapfill import BitgetRestGapFillWorker
from market_stream.provider_diagnostics import ProviderDiagnostics
from market_stream.sinks.eventbus import AsyncRedisEventBus
from market_stream.sinks.postgres_raw import PostgresRawSink
from market_stream.sinks.redis_stream import RedisStreamSink
from market_stream.storage.candles_repo import CandlesRepository
from market_stream.storage.orderbook_repo import OrderBookRepository
from market_stream.storage.ticker_repo import TickerRepository
from market_stream.storage.trades_repo import TradesRepository


class MarketStreamSettings(BitgetSettings):
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

    market_stream_port: int = Field(default=8010, alias="MARKET_STREAM_PORT")
    market_stream_ws_mode: Literal["classic", "uta"] = Field(
        default="classic",
        alias="MARKET_STREAM_WS_MODE",
    )
    market_stream_enable_raw_persist: bool = Field(
        default=False,
        alias="MARKET_STREAM_ENABLE_RAW_PERSIST",
    )
    market_stream_ws_stale_after_sec: int = Field(
        default=60,
        alias="MARKET_STREAM_WS_STALE_AFTER_SEC",
    )
    market_stream_stale_escalation_max_cycles: int = Field(
        default=12,
        alias="MARKET_STREAM_STALE_ESCALATION_MAX_CYCLES",
    )
    market_stream_ready_max_data_age_sec: int = Field(
        default=180,
        alias="MARKET_STREAM_READY_MAX_DATA_AGE_SEC",
    )
    market_stream_ready_boot_grace_sec: int = Field(
        default=90,
        alias="MARKET_STREAM_READY_BOOT_GRACE_SEC",
    )
    market_stream_ready_require_fresh_trades: bool = Field(
        default=False,
        alias="MARKET_STREAM_READY_REQUIRE_FRESH_TRADES",
    )
    market_stream_ready_allow_metadata_degraded: bool = Field(
        default=False,
        alias="MARKET_STREAM_READY_ALLOW_METADATA_DEGRADED",
        description=(
            "Lokal/Staging: /ready akzeptiert instrument_metadata-Status 'degraded' "
            "(nur 'unavailable' blockiert). In Production false lassen."
        ),
    )
    market_stream_feed_health_interval_sec: int = Field(
        default=10,
        alias="MARKET_STREAM_FEED_HEALTH_INTERVAL_SEC",
    )
    orderbook_max_levels: int = Field(default=50, alias="ORDERBOOK_MAX_LEVELS")
    orderbook_checksum_levels: int = Field(default=25, alias="ORDERBOOK_CHECKSUM_LEVELS")
    orderbook_resync_on_mismatch: bool = Field(
        default=True,
        alias="ORDERBOOK_RESYNC_ON_MISMATCH",
    )
    slippage_sizes_usdt_raw: str = Field(
        default="1000,5000,10000",
        alias="SLIPPAGE_SIZES_USDT",
    )
    oi_snapshot_interval_sec: int = Field(default=30, alias="OI_SNAPSHOT_INTERVAL_SEC")
    funding_snapshot_interval_sec: int = Field(
        default=60,
        alias="FUNDING_SNAPSHOT_INTERVAL_SEC",
    )
    symbol_price_snapshot_interval_sec: int = Field(
        default=5,
        alias="SYMBOL_PRICE_SNAPSHOT_INTERVAL_SEC",
    )
    eventbus_default_block_ms: int = Field(
        default=2000,
        alias="EVENTBUS_DEFAULT_BLOCK_MS",
    )
    eventbus_default_count: int = Field(default=50, alias="EVENTBUS_DEFAULT_COUNT")
    eventbus_dedupe_ttl_sec: int = Field(
        default=86400,
        alias="EVENTBUS_DEDUPE_TTL_SEC",
    )
    bitget_candle_initial_load_limit: int = Field(
        default=300,
        alias="BITGET_CANDLE_INITIAL_LOAD_LIMIT",
    )
    bitget_candle_kline_type: str = Field(
        default="MARKET",
        alias="BITGET_CANDLE_KLINE_TYPE",
    )
    tsdb_retention_days_candles_1m: int = Field(
        default=45,
        alias="TSDB_RETENTION_DAYS_CANDLES_1M",
    )
    tsdb_retention_days_candles_5m: int = Field(
        default=90,
        alias="TSDB_RETENTION_DAYS_CANDLES_5M",
    )
    tsdb_retention_days_candles_15m: int = Field(
        default=180,
        alias="TSDB_RETENTION_DAYS_CANDLES_15M",
    )
    tsdb_retention_days_candles_1h: int = Field(
        default=365,
        alias="TSDB_RETENTION_DAYS_CANDLES_1H",
    )
    tsdb_retention_days_candles_4h: int = Field(
        default=730,
        alias="TSDB_RETENTION_DAYS_CANDLES_4H",
    )
    @field_validator("market_stream_port")
    @classmethod
    def _validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("MARKET_STREAM_PORT muss zwischen 1 und 65535 liegen")
        return value

    @field_validator(
        "market_stream_ws_stale_after_sec",
        "market_stream_ready_max_data_age_sec",
        "market_stream_ready_boot_grace_sec",
    )
    @classmethod
    def _validate_positive_sec(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Zeitfenster in Sekunden muss > 0 sein")
        return value

    @field_validator("market_stream_stale_escalation_max_cycles")
    @classmethod
    def _validate_escalation_cycles(cls, value: int) -> int:
        if value < 1:
            raise ValueError("MARKET_STREAM_STALE_ESCALATION_MAX_CYCLES muss >= 1 sein")
        return value

    @field_validator("market_stream_feed_health_interval_sec")
    @classmethod
    def _validate_feed_health_interval(cls, value: int) -> int:
        if not 3 <= value <= 600:
            raise ValueError("MARKET_STREAM_FEED_HEALTH_INTERVAL_SEC muss 3..600 sein")
        return value

    @field_validator("bitget_candle_initial_load_limit")
    @classmethod
    def _validate_initial_load_limit(cls, value: int) -> int:
        if not 1 <= value <= 1000:
            raise ValueError("BITGET_CANDLE_INITIAL_LOAD_LIMIT muss zwischen 1 und 1000 liegen")
        return value

    @field_validator("orderbook_max_levels")
    @classmethod
    def _validate_orderbook_max_levels(cls, value: int) -> int:
        if value < 25:
            raise ValueError("ORDERBOOK_MAX_LEVELS muss mindestens 25 sein")
        return value

    @field_validator("orderbook_checksum_levels")
    @classmethod
    def _validate_orderbook_checksum_levels(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ORDERBOOK_CHECKSUM_LEVELS muss > 0 sein")
        return value

    @field_validator(
        "oi_snapshot_interval_sec",
        "funding_snapshot_interval_sec",
        "symbol_price_snapshot_interval_sec",
        "eventbus_default_block_ms",
        "eventbus_default_count",
    )
    @classmethod
    def _validate_snapshot_interval(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Snapshot-Intervalle muessen > 0 sein")
        return value

    @field_validator("eventbus_dedupe_ttl_sec")
    @classmethod
    def _validate_dedupe_ttl(cls, value: int) -> int:
        if value < 0:
            raise ValueError("EVENTBUS_DEDUPE_TTL_SEC darf nicht negativ sein")
        return value

    @field_validator("bitget_candle_kline_type", mode="before")
    @classmethod
    def _normalize_kline_type(cls, value: object) -> str:
        if value is None:
            return "MARKET"
        return str(value).strip().upper() or "MARKET"

    @field_validator("slippage_sizes_usdt_raw", mode="before")
    @classmethod
    def _normalize_slippage_sizes(cls, value: object) -> str:
        if value is None:
            return "1000,5000,10000"
        parts = [part.strip() for part in str(value).split(",") if part.strip()]
        if not parts:
            raise ValueError("SLIPPAGE_SIZES_USDT darf nicht leer sein")
        for part in parts:
            if int(part) <= 0:
                raise ValueError("SLIPPAGE_SIZES_USDT darf nur positive Werte enthalten")
        return ",".join(parts)

    @field_validator(
        "tsdb_retention_days_candles_1m",
        "tsdb_retention_days_candles_5m",
        "tsdb_retention_days_candles_15m",
        "tsdb_retention_days_candles_1h",
        "tsdb_retention_days_candles_4h",
    )
    @classmethod
    def _validate_retention_days(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Retention-Tage muessen > 0 sein")
        return value

    @model_validator(mode="after")
    def _validate_orderbook_relationships(self) -> MarketStreamSettings:
        if self.orderbook_checksum_levels > self.orderbook_max_levels:
            raise ValueError("ORDERBOOK_CHECKSUM_LEVELS darf ORDERBOOK_MAX_LEVELS nicht uebersteigen")
        return self

    @property
    def candle_retention_days(self) -> dict[str, int]:
        return {
            "1m": self.tsdb_retention_days_candles_1m,
            "5m": self.tsdb_retention_days_candles_5m,
            "15m": self.tsdb_retention_days_candles_15m,
            "1H": self.tsdb_retention_days_candles_1h,
            "4H": self.tsdb_retention_days_candles_4h,
        }

    @property
    def slippage_sizes_usdt(self) -> list[int]:
        return [int(value) for value in self.slippage_sizes_usdt_raw.split(",")]


class MarketStreamRuntime:
    def __init__(self, settings: MarketStreamSettings) -> None:
        self._logger = logging.getLogger("market_stream")
        self._settings = settings
        self._bitget_settings: BitgetSettings = settings
        self._catalog = BitgetInstrumentCatalog(
            bitget_settings=self._bitget_settings,
            database_url=settings.database_url,
            redis_url=settings.redis_url,
            source_service="market-stream",
            cache_ttl_sec=settings.instrument_catalog_cache_ttl_sec,
            max_stale_sec=settings.instrument_catalog_max_stale_sec,
        )
        self._metadata_service = BitgetInstrumentMetadataService(self._catalog)
        self._catalog_entry = None
        self._metadata = None
        self._catalog_block_reason: str | None = None
        self._stats = ClientRuntimeStats(
            ws_mode=settings.market_stream_ws_mode,
            started_at_ms=int(time.time() * 1000),
        )
        self._provider_diagnostics = ProviderDiagnostics()
        self._redis_sink = RedisStreamSink(settings.redis_url, logger=self._logger)
        self._slippage_sink = RedisStreamSink(
            settings.redis_url,
            stream_key="stream:market:slippage_metrics",
            logger=self._logger,
        )
        self._event_bus = AsyncRedisEventBus(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
            logger=self._logger,
        )
        self._postgres_sink = PostgresRawSink(
            settings.database_url,
            enabled=settings.market_stream_enable_raw_persist,
            logger=self._logger,
        )
        self._candles_repo = CandlesRepository(
            settings.database_url,
            logger=self._logger,
        )
        self._trades_repo = TradesRepository(
            settings.database_url,
            logger=self._logger,
        )
        self._ticker_repo = TickerRepository(
            settings.database_url,
            logger=self._logger,
        )
        self._orderbook_repo = OrderBookRepository(
            settings.database_url,
            logger=self._logger,
        )
        self._candle_collector = CandleCollector(
            bitget_settings=self._bitget_settings,
            candles_repo=self._candles_repo,
            event_bus=self._event_bus,
            logger=self._logger,
            initial_load_limit=settings.bitget_candle_initial_load_limit,
            kline_type=settings.bitget_candle_kline_type,
            retention_days_by_timeframe=settings.candle_retention_days,
            catalog_entry_provider=self._catalog_entry_provider,
            provider_diagnostics=self._provider_diagnostics,
        )
        self._trades_collector = TradesCollector(
            bitget_settings=self._bitget_settings,
            trades_repo=self._trades_repo,
            logger=self._logger,
        )
        self._ticker_collector = TickerCollector(
            bitget_settings=self._bitget_settings,
            ticker_repo=self._ticker_repo,
            event_bus=self._event_bus,
            oi_snapshot_interval_sec=settings.oi_snapshot_interval_sec,
            funding_snapshot_interval_sec=settings.funding_snapshot_interval_sec,
            symbol_price_snapshot_interval_sec=settings.symbol_price_snapshot_interval_sec,
            logger=self._logger,
            catalog_entry_provider=self._catalog_entry_provider,
            provider_diagnostics=self._provider_diagnostics,
        )
        self._orderbook_collector = OrderbookCollector(
            bitget_settings=self._bitget_settings,
            orderbook_repo=self._orderbook_repo,
            slippage_sink=self._slippage_sink,
            max_levels=settings.orderbook_max_levels,
            checksum_levels=settings.orderbook_checksum_levels,
            resync_on_mismatch=settings.orderbook_resync_on_mismatch,
            slippage_sizes_usdt=settings.slippage_sizes_usdt,
            logger=self._logger,
        )
        self._gapfill_worker = BitgetRestGapFillWorker(
            bitget_settings=self._bitget_settings,
            redis_sink=self._redis_sink,
            postgres_sink=self._postgres_sink,
            logger=self._logger,
            on_complete=self._after_rest_gapfill,
            provider_diagnostics=self._provider_diagnostics,
        )
        if settings.market_stream_ws_mode == "uta":
            self._logger.warning(
                "MARKET_STREAM_WS_MODE=uta ist vorbereitet, verwendet in Prompt 5 "
                "aber weiterhin die klassische productType-basierte instType-Belegung."
            )
        self._client = BitgetPublicWsClient(
            bitget_settings=self._bitget_settings,
            rate_limiter=RateLimiter(max_per_sec=10),
            redis_sink=self._redis_sink,
            postgres_sink=self._postgres_sink,
            gapfill_worker=self._gapfill_worker,
            stats=self._stats,
            logger=self._logger,
            ws_mode=settings.market_stream_ws_mode,
            stale_after_sec=settings.market_stream_ws_stale_after_sec,
            stale_escalation_max_cycles=settings.market_stream_stale_escalation_max_cycles,
            provider_diagnostics=self._provider_diagnostics,
            initial_subscriptions=[
                *self._ticker_collector.subscriptions(),
                *self._trades_collector.subscriptions(),
                *self._orderbook_collector.subscriptions(),
                *self._candle_collector.subscriptions(),
            ],
            message_handlers=[
                self._orderbook_collector.handle_ws_message,
                self._trades_collector.handle_ws_message,
                self._ticker_collector.handle_ws_message,
                self._candle_collector.handle_ws_message,
            ],
            connected_callbacks=[
                self._orderbook_collector.on_connected,
                self._ticker_collector.on_connected,
                self._candle_collector.on_connected,
            ],
        )
        self._orderbook_collector.bind_resync_action(self._resync_orderbook)
        self._runner_task: asyncio.Task[None] | None = None
        self._feed_health_task: asyncio.Task[None] | None = None
        self._catalog_refresh_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._stats.connection_state = "starting"
        try:
            await asyncio.to_thread(
                self._catalog.refresh_catalog,
                refresh_reason="startup",
            )
            self._catalog_entry = await asyncio.to_thread(
                self._catalog.current_configured_instrument,
                refresh_if_missing=False,
                require_subscription=True,
            )
            self._metadata = await asyncio.to_thread(
                self._metadata_service.resolve_for_subscription,
                symbol=self._bitget_settings.symbol,
                market_family=self._bitget_settings.market_family,
                product_type=(
                    self._bitget_settings.product_type
                    if self._bitget_settings.market_family == "futures"
                    else None
                ),
                margin_account_mode=(
                    self._bitget_settings.margin_account_mode
                    if self._bitget_settings.market_family == "margin"
                    else None
                ),
                refresh_if_missing=False,
            )
            self._catalog_block_reason = None
        except Exception as exc:
            self._catalog_entry = None
            self._metadata = None
            self._catalog_block_reason = str(exc)
            self._stats.connection_state = "catalog_blocked"
            self._logger.error(
                "market-stream catalog blocked symbol=%s family=%s reason=%s",
                self._bitget_settings.symbol,
                self._bitget_settings.market_family,
                exc,
            )
            return
        await self._redis_sink.connect()
        await self._event_bus.connect()
        if self._settings.market_stream_enable_raw_persist:
            await self._postgres_sink.connect()
        await self._candle_collector.start()
        await self._trades_collector.start()
        await self._ticker_collector.start()
        await self._orderbook_collector.start()
        self._sync_sink_stats()
        self._runner_task = asyncio.create_task(
            self._client.run(),
            name="market-stream-ws-client",
        )
        self._runner_task.add_done_callback(self._on_runner_task_done)
        self._feed_health_task = asyncio.create_task(
            self._feed_health_loop(),
            name="market-stream-feed-health",
        )
        self._catalog_refresh_task = asyncio.create_task(
            self._catalog_refresh_loop(),
            name="market-stream-catalog-refresh",
        )
        self._logger.info(
            "market-stream runtime started on port %s for symbol %s family=%s",
            self._settings.market_stream_port,
            self._bitget_settings.symbol,
            self._bitget_settings.market_family,
        )

    async def stop(self) -> None:
        if self._catalog_refresh_task is not None:
            self._catalog_refresh_task.cancel()
            await asyncio.gather(self._catalog_refresh_task, return_exceptions=True)
            self._catalog_refresh_task = None
        if self._feed_health_task is not None:
            self._feed_health_task.cancel()
            await asyncio.gather(self._feed_health_task, return_exceptions=True)
            self._feed_health_task = None
        await self._client.stop()
        if self._runner_task is not None:
            self._runner_task.cancel()
            await asyncio.gather(self._runner_task, return_exceptions=True)
        await self._orderbook_collector.stop()
        await self._ticker_collector.stop()
        await self._trades_collector.stop()
        await self._candle_collector.stop()
        await self._redis_sink.close()
        await self._slippage_sink.close()
        await self._event_bus.close()
        await self._postgres_sink.close()
        self._sync_sink_stats()
        self._stats.connection_state = "stopped"
        self._logger.info("market-stream runtime stopped")

    def health_payload(self) -> dict[str, object]:
        self._sync_sink_stats()
        catalog_health = self._catalog.health_payload()
        metadata_health = self._metadata_service.health_payload()
        return {
            "status": (
                "ok"
                if self._catalog_block_reason is None and metadata_health.get("status") == "ok"
                else "degraded"
            ),
            "service": "market-stream",
            "connection_state": self._stats.connection_state,
            "ws_connected": self._stats.connection_state == "connected",
            "redis_connected": self._stats.redis_connected,
            "postgres_connected": self._stats.postgres_connected,
            "eventbus_connected": self._event_bus.is_connected,
            "candle_store_connected": self._candles_repo.is_connected,
            "trades_store_connected": self._trades_repo.is_connected,
            "ticker_store_connected": self._ticker_repo.is_connected,
            "orderbook_store_connected": self._orderbook_repo.is_connected,
            "effective_ws_public_url": self._bitget_settings.effective_ws_public_url,
            "symbol": self._bitget_settings.symbol,
            "market_family": self._bitget_settings.market_family,
            "instrument": (
                self._catalog_entry.identity().model_dump(mode="json")
                if self._catalog_entry is not None
                else self._bitget_settings.instrument_identity().model_dump(mode="json")
            ),
            "instrument_catalog": catalog_health,
            "instrument_metadata": metadata_health,
            "catalog_block_reason": self._catalog_block_reason,
            "candle_initial_load_complete": self._candle_collector.initial_load_complete,
            "orderbook_desynced": self._orderbook_collector.stats_payload()["orderbook_desynced"],
            "gapfill_last_ok_ts_ms": self._gapfill_worker.last_gapfill_ok_ts_ms,
            "gapfill_last_reason": self._gapfill_worker.last_gapfill_reason,
            "stale_escalation_count": self._stats.stale_escalation_count,
            "tracked_seq_channels": self._stats.tracked_seq_channels,
            "last_seq_channel_key": self._stats.last_seq_channel_key,
            "bitget_ws_stream": self._ws_stream_telemetry(),
            "ingest": self._ingest_feed_snapshot(),
        }

    def stats_payload(self) -> dict[str, object]:
        self._sync_sink_stats()
        return {
            "service": "market-stream",
            "ws_mode": self._stats.ws_mode,
            "subscriptions": self._stats.active_subscriptions,
            "last_seq": self._stats.last_seq,
            "last_seq_channel_key": self._stats.last_seq_channel_key,
            "tracked_seq_channels": self._stats.tracked_seq_channels,
            "stale_escalation_count": self._stats.stale_escalation_count,
            "last_event_ts": self._stats.last_event_ts_ms,
            "gapfill_last_ok_ts_ms": self._gapfill_worker.last_gapfill_ok_ts_ms,
            "gapfill_last_reason": self._gapfill_worker.last_gapfill_reason,
            "last_ping_ts": self._stats.last_ping_ts_ms,
            "last_pong_ts": self._stats.last_pong_ts_ms,
            "published_events": self._stats.published_events,
            "reconnect_count": self._stats.reconnect_count,
            "last_reconnect_at_ms": self._stats.last_reconnect_at_ms,
            "connection_state": self._stats.connection_state,
            "eventbus_connected": self._event_bus.is_connected,
            "candle_store_connected": self._candles_repo.is_connected,
            "last_error": self._stats.last_error,
            "started_at_ms": self._stats.started_at_ms,
            "bitget_ws_stream": self._ws_stream_telemetry(),
            "instrument_catalog": self._catalog.health_payload(),
            "instrument_metadata": self._metadata_service.health_payload(),
            **self._trades_collector.stats_payload(),
            **self._ticker_collector.stats_payload(),
            **self._orderbook_collector.stats_payload(),
            **self._candle_collector.stats_payload(),
            "ingest": self._ingest_feed_snapshot(),
        }

    def _ingest_feed_snapshot(self) -> dict[str, Any]:
        return {
            "universe_note": (
                "Alle Kerzen/Ticker-Pfade nutzen BITGET_SYMBOL und Katalog-Metadaten — "
                "kein implizites BTC-only; Multi-Symbol erfordert weitere Instanzen oder zukuenftige Fan-out-Erweiterung."
            ),
            "configured_symbol": self._bitget_settings.symbol,
            "market_family": self._bitget_settings.market_family,
            "candles": {
                "timeframe_to_channel": dict(TIMEFRAME_TO_CHANNEL),
                "last_close_event_ingest_ts_ms": self._candle_collector.last_close_event_ts_ms,
                "last_persist_ts_ms": self._candle_collector.last_candle_persist_ts_ms,
                "last_successful_bar": self._candle_collector.last_successful_candle_bar(),
            },
            "ticker": {
                "last_quote_ts_ms": self._ticker_collector.last_quote_ts_ms(),
                "last_ws_ticker_ts_ms": self._ticker_collector.last_ws_ticker_ts_ms(),
                "last_rest_snapshot_ts_ms": self._ticker_collector.last_rest_snapshot_ts_ms(),
            },
            "reconnect": {
                "ws_connection_state": self._stats.connection_state,
                "ws_reconnect_count": self._stats.reconnect_count,
                "last_ws_reconnect_at_ms": self._stats.last_reconnect_at_ms,
            },
            "provider_surface": self._provider_diagnostics.as_health_fragment(),
            "gapfill": {
                "last_ok_ts_ms": self._gapfill_worker.last_gapfill_ok_ts_ms,
                "last_reason": self._gapfill_worker.last_gapfill_reason,
                "last_error": self._gapfill_worker.last_gapfill_error,
            },
        }

    def _sync_sink_stats(self) -> None:
        self._stats.redis_connected = self._redis_sink.is_connected
        self._stats.postgres_connected = self._postgres_sink.is_connected

    def _catalog_entry_provider(self):
        return self._catalog_entry

    def _catalog_instrument(self):
        if self._catalog_entry is not None:
            return self._catalog_entry.identity()
        return self._bitget_settings.instrument_identity()

    async def _resync_orderbook(self, reason: str) -> None:
        self._logger.warning("runtime orderbook resync started reason=%s", reason)
        for channel in ("books", "books5"):
            await self._client.unsubscribe(
                self._bitget_settings.public_ws_inst_type,
                channel,
                self._bitget_settings.symbol,
            )
        for channel in ("books5", "books"):
            await self._client.subscribe(
                self._bitget_settings.public_ws_inst_type,
                channel,
                self._bitget_settings.symbol,
            )

    async def _after_rest_gapfill(self, reason: str) -> None:
        await self._ticker_collector.refresh_rest_snapshots(reason=f"gapfill-{reason}")
        if gapfill_triggers_orderbook_resync(reason):
            await self._resync_orderbook(f"gapfill-{reason}")

    def _evaluate_data_freshness(self) -> tuple[bool, str, dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        boot_age_ms = now_ms - int(self._stats.started_at_ms)
        grace_ms = self._settings.market_stream_ready_boot_grace_sec * 1000
        if boot_age_ms < grace_ms:
            meta = {"boot_age_ms": boot_age_ms, "grace_ms": grace_ms}
            return True, "boot_grace", meta

        max_age_ms = self._settings.market_stream_ready_max_data_age_sec * 1000
        tq = self._ticker_collector.last_quote_ts_ms()
        ob = self._orderbook_collector.last_orderbook_ts_ms()
        tr = self._trades_collector.last_trade_ts_ms()
        age_t, age_o = compute_quote_age_ms(
            now_ms=now_ms,
            last_quote_ts_ms=tq,
            last_orderbook_ts_ms=ob,
        )
        age_tr = (now_ms - tr) if tr else None
        detail: dict[str, Any] = {
            "age_ticker_ms": age_t,
            "age_orderbook_ms": age_o,
            "age_trade_ms": age_tr,
            "ready_max_age_ms": max_age_ms,
        }
        reasons: list[str] = []
        if tq is None or (age_t is not None and age_t > max_age_ms):
            reasons.append("ticker_stale")
        if ob is None or (age_o is not None and age_o > max_age_ms):
            reasons.append("orderbook_stale")
        if self._settings.market_stream_ready_require_fresh_trades and (
            tr is None or (age_tr is not None and age_tr > max_age_ms)
        ):
            reasons.append("trades_stale")
        if not reasons:
            return True, "ok", detail
        return False, ",".join(reasons), detail

    def _ws_stream_telemetry(self) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        last_ev = self._stats.last_event_ts_ms
        last_age = (now_ms - last_ev) if last_ev is not None else None
        ok, reason, ages = self._evaluate_data_freshness()
        try:
            coverage = self._client.subscription_coverage()
        except Exception:
            coverage = []
        return {
            "connection_state": self._stats.connection_state,
            "subscription_coverage": coverage,
            "last_event_ts_ms": last_ev,
            "last_event_age_ms": last_age,
            "last_exchange_ts_ms": self._stats.last_exchange_ts_ms,
            "last_ingest_latency_ms": self._stats.last_ingest_latency_ms,
            "gap_events_count": self._stats.gap_events_count,
            "stale_escalation_count": self._stats.stale_escalation_count,
            "gapfill_last_ok_ts_ms": self._gapfill_worker.last_gapfill_ok_ts_ms,
            "gapfill_last_reason": self._gapfill_worker.last_gapfill_reason,
            "data_freshness_ok": ok,
            "data_freshness_reason": reason,
            "age_ticker_ms": ages.get("age_ticker_ms"),
            "age_orderbook_ms": ages.get("age_orderbook_ms"),
            "age_trade_ms": ages.get("age_trade_ms"),
            "last_reconnect_at_ms": self._stats.last_reconnect_at_ms,
            "ws_reconnect_count": self._stats.reconnect_count,
        }

    async def _feed_health_loop(self) -> None:
        interval = float(self._settings.market_stream_feed_health_interval_sec)
        while True:
            await asyncio.sleep(interval)
            try:
                touch_worker_heartbeat("market_stream")
                ok, reason, ages = self._evaluate_data_freshness()
                ob = self._orderbook_collector.stats_payload()
                desynced = bool(ob.get("orderbook_desynced"))
                ws_ok = self._stats.connection_state == "connected"
                payload: dict[str, Any] = {
                    "ok": ok and not desynced and ws_ok,
                    "ws_connected": ws_ok,
                    "symbol": self._bitget_settings.symbol,
                    "market_family": self._bitget_settings.market_family,
                    "connection_state": self._stats.connection_state,
                    "reasons": ([] if ok else [reason])
                    + (["orderbook_desynced"] if desynced else []),
                    "age_ticker_ms": ages.get("age_ticker_ms"),
                    "age_orderbook_ms": ages.get("age_orderbook_ms"),
                    "age_trade_ms": ages.get("age_trade_ms"),
                    "ready_max_age_ms": ages.get("ready_max_age_ms"),
                    "orderbook_desynced": desynced,
                    "last_gapfill_reason": self._gapfill_worker.last_gapfill_reason,
                    "stale_escalation_count": self._stats.stale_escalation_count,
                    "gapfill_last_ok_ts_ms": self._gapfill_worker.last_gapfill_ok_ts_ms,
                    "gapfill_last_error": self._gapfill_worker.last_gapfill_error,
                    "ingest": self._ingest_feed_snapshot(),
                }
                if reason == "boot_grace":
                    payload["ok"] = ws_ok and not desynced
                    payload["reasons"] = ["boot_grace"]
                await publish_market_feed_health(
                    self._event_bus,
                    symbol=self._bitget_settings.symbol,
                    payload=payload,
                    instrument=self._catalog_instrument(),
                    logger=self._logger,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.warning("feed health loop error: %s", exc)

    async def _catalog_refresh_loop(self) -> None:
        interval = float(self._settings.instrument_catalog_refresh_interval_sec)
        while True:
            await asyncio.sleep(interval)
            try:
                await asyncio.to_thread(
                    self._catalog.refresh_catalog,
                    refresh_reason="periodic_refresh",
                )
                self._catalog_entry = await asyncio.to_thread(
                    self._catalog.current_configured_instrument,
                    refresh_if_missing=False,
                    require_subscription=True,
                )
                self._metadata = await asyncio.to_thread(
                    self._metadata_service.resolve_for_subscription,
                    symbol=self._bitget_settings.symbol,
                    market_family=self._bitget_settings.market_family,
                    product_type=(
                        self._bitget_settings.product_type
                        if self._bitget_settings.market_family == "futures"
                        else None
                    ),
                    margin_account_mode=(
                        self._bitget_settings.margin_account_mode
                        if self._bitget_settings.market_family == "margin"
                        else None
                    ),
                    refresh_if_missing=False,
                )
                self._catalog_block_reason = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._catalog_block_reason = str(exc)
                self._logger.warning("instrument catalog refresh failed: %s", exc)

    def _on_runner_task_done(self, task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception as exc:  # pragma: no cover - callback logging path
            self._stats.last_error = str(exc)
            self._stats.connection_state = "error"
            self._logger.exception("market-stream background task crashed", exc_info=exc)


def _instrument_metadata_ready_ok(
    runtime: MarketStreamRuntime,
    *,
    allow_degraded: bool,
) -> bool:
    if runtime._catalog_block_reason is not None:
        return False
    st = str(runtime._metadata_service.health_payload().get("status") or "unavailable")
    if st == "ok":
        return True
    if allow_degraded and st == "degraded":
        return True
    return False


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings

    settings = MarketStreamSettings()
    bootstrap_from_settings("market-stream", settings)
    wait_for_datastores(
        settings.database_url,
        settings.redis_url,
        logger=logging.getLogger("market_stream"),
        service_name="market-stream",
    )
    runtime = MarketStreamRuntime(settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = FastAPI(
        title="market-stream",
        version="0.1.0",
        description="Bitget public market stream service.",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, object]:
        return runtime.health_payload()

    @app.get("/stats")
    async def stats() -> dict[str, object]:
        return runtime.stats_payload()

    @app.get("/ready")
    async def ready() -> dict[str, object]:
        ob = runtime._orderbook_collector.stats_payload()
        desynced = bool(ob.get("orderbook_desynced"))
        fresh_ok, fresh_detail, _fmeta = runtime._evaluate_data_freshness()
        parts = {
            "postgres": check_postgres(settings.database_url),
            "redis": check_redis_url(settings.redis_url),
            "eventbus": (
                runtime._event_bus.is_connected,
                "connected" if runtime._event_bus.is_connected else "not_connected",
            ),
            "ws_feed": (
                runtime._stats.connection_state == "connected",
                f"state={runtime._stats.connection_state!r}",
            ),
            "candle_initial_load": (
                runtime._candle_collector.initial_load_complete,
                "complete" if runtime._candle_collector.initial_load_complete else "pending",
            ),
            "orderbook_consistent": (
                not desynced,
                "ok" if not desynced else "orderbook_desynced",
            ),
            "data_freshness": (
                fresh_ok,
                fresh_detail,
            ),
            "instrument_catalog": (
                runtime._catalog_block_reason is None,
                runtime._catalog_block_reason or runtime._catalog.health_payload().get("status", "ok"),
            ),
            "instrument_metadata": (
                _instrument_metadata_ready_ok(
                    runtime,
                    allow_degraded=settings.market_stream_ready_allow_metadata_degraded,
                ),
                runtime._metadata_service.health_payload().get("status", "unavailable"),
            ),
        }
        ok, details = merge_ready_details(parts)
        return {"ready": ok, "checks": details}

    instrument_fastapi(app, "market-stream")
    return app

