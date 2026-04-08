from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import psycopg
from redis.exceptions import RedisError
from shared_py.eventbus import ConsumedEvent, EventEnvelope, RedisStreamBus
from shared_py.observability import touch_worker_heartbeat

from signal_engine.config import SignalEngineSettings, normalize_timeframe
from signal_engine.events.publisher import publish_signal_created
from signal_engine.operator_intel_publish import publish_signal_operator_intel
from signal_engine.service import SignalEngineService

KNOWN_TF = {"1m", "5m", "15m", "1H", "4H"}


@dataclass(slots=True)
class SignalWorkerStats:
    running: bool = False
    redis_connected: bool = False
    db_connected: bool = False
    group_ready: bool = False
    consumed_events: int = 0
    processed_events: int = 0
    dlq_events: int = 0
    last_event_id: str | None = None
    last_error: str | None = None


class SignalWorker:
    def __init__(
        self,
        settings: SignalEngineSettings,
        service: SignalEngineService,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._service = service
        self._logger = logger or logging.getLogger("signal_engine.worker")
        self._stats = SignalWorkerStats()
        self._stop_event = asyncio.Event()
        self._bus = RedisStreamBus.from_url(
            settings.redis_url,
            dedupe_ttl_sec=settings.eventbus_dedupe_ttl_sec,
            default_block_ms=settings.eventbus_default_block_ms,
            default_count=settings.eventbus_default_count,
        )

    def stats_payload(self) -> dict[str, object]:
        return {
            "running": self._stats.running,
            "redis_connected": self._stats.redis_connected,
            "db_connected": self._stats.db_connected,
            "group_ready": self._stats.group_ready,
            "stream": self._settings.signal_stream,
            "group": self._settings.signal_group,
            "consumer": self._settings.signal_consumer,
            "consumed_events": self._stats.consumed_events,
            "processed_events": self._stats.processed_events,
            "dlq_events": self._stats.dlq_events,
            "last_event_id": self._stats.last_event_id,
            "last_error": self._stats.last_error,
        }

    async def run(self) -> None:
        self._stats.running = True
        try:
            while not self._stop_event.is_set():
                try:
                    await self._ensure_group()
                    items = await asyncio.to_thread(
                        self._bus.consume,
                        self._settings.signal_stream,
                        self._settings.signal_group,
                        self._settings.signal_consumer,
                        self._settings.eventbus_default_count,
                        self._settings.eventbus_default_block_ms,
                    )
                    self._stats.redis_connected = True
                    touch_worker_heartbeat("signal_engine")
                    if not items:
                        continue
                    for item in items:
                        await self._handle_item(item)
                except asyncio.CancelledError:
                    raise
                except (OSError, RedisError) as exc:
                    self._stats.redis_connected = False
                    self._stats.group_ready = False
                    self._stats.last_error = str(exc)
                    self._logger.warning("signal worker redis error: %s", exc)
                    await asyncio.sleep(2)
                except Exception as exc:
                    self._stats.last_error = str(exc)
                    self._logger.exception("signal worker loop failed", exc_info=exc)
                    await asyncio.sleep(2)
        finally:
            self._stats.running = False
            await self.close()

    async def stop(self) -> None:
        self._stop_event.set()

    async def close(self) -> None:
        await asyncio.to_thread(self._bus.redis.close)

    async def _ensure_group(self) -> None:
        if self._stats.group_ready:
            return
        await asyncio.to_thread(
            self._bus.ensure_group,
            self._settings.signal_stream,
            self._settings.signal_group,
        )
        self._stats.group_ready = True

    async def _handle_item(self, item: ConsumedEvent) -> None:
        self._stats.consumed_events += 1
        self._stats.last_event_id = item.envelope.event_id
        try:
            bundle = await asyncio.to_thread(self._process_envelope, item.envelope)
            self._stats.db_connected = True
            self._stats.processed_events += 1
            if bundle is not None:
                merged_trace: dict[str, object] = {
                    "source_event_id": item.envelope.event_id,
                }
                if item.envelope.trace:
                    merged_trace.update(dict(item.envelope.trace))
                snap = bundle["event_payload"].get("correlation_chain")
                if isinstance(snap, dict):
                    merged_trace["correlation_chain"] = dict(snap)
                await asyncio.to_thread(
                    publish_signal_created,
                    self._bus,
                    symbol=bundle["event_payload"]["symbol"],
                    timeframe=bundle["event_payload"]["timeframe"],
                    payload=bundle["event_payload"],
                    dedupe_key=f"signal:{bundle['event_payload']['signal_id']}",
                    trace=merged_trace,
                    logger=self._logger,
                )
                if self._settings.signal_operator_intel_outbox_enabled:
                    await asyncio.to_thread(
                        publish_signal_operator_intel,
                        self._bus,
                        bundle,
                        logger_=self._logger,
                    )
            await self._ack(item)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._stats.last_error = str(exc)
            if isinstance(exc, psycopg.Error):
                self._stats.db_connected = False
            await self._publish_dlq(item, exc)
            await self._ack(item)
            self._logger.warning(
                "signal worker DLQ event_id=%s error=%s",
                item.envelope.event_id,
                exc,
            )

    def _process_envelope(self, env: EventEnvelope) -> dict[str, object] | None:
        if env.event_type != "drawing_updated":
            self._logger.debug("skip event_type=%s", env.event_type)
            return None
        symbol = str(env.symbol).strip()
        tf = normalize_timeframe(_tf_from_envelope(env))
        if tf not in KNOWN_TF:
            self._logger.debug("skip timeframe=%s", tf)
            return None
        pl = env.payload
        ts_ms = int(pl.get("ts_ms") or env.exchange_ts_ms or env.ingest_ts_ms)
        ct = dict(env.trace) if env.trace else {}
        return self._service.evaluate_and_persist(
            symbol,
            tf,
            ts_ms,
            causal_trace=ct,
            upstream_event_id=str(env.event_id),
        )

    async def _publish_dlq(self, item: ConsumedEvent, exc: Exception) -> None:
        await asyncio.to_thread(
            self._bus.publish_dlq,
            item.envelope,
            {"stage": "signal_worker", "error": str(exc)},
        )
        self._stats.dlq_events += 1

    async def _ack(self, item: ConsumedEvent) -> None:
        await asyncio.to_thread(
            self._bus.ack,
            item.stream,
            self._settings.signal_group,
            item.message_id,
        )


def _tf_from_envelope(env: EventEnvelope) -> str:
    if env.timeframe and str(env.timeframe).strip():
        return str(env.timeframe).strip()
    raw = env.payload.get("timeframe")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    raise ValueError("drawing_updated ohne timeframe")
