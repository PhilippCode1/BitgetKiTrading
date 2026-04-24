from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import websockets
from shared_py.bitget.config import BitgetSettings
from shared_py.observability.metrics import inc_pipeline_event_drop
from shared_py.observability.provider_log import provider_log_extra

from market_stream.bitget_ws.rate_limiter import RateLimiter
from market_stream.bitget_ws.sequence_buffer import BitgetWsSequenceBuffer
from market_stream.bitget_ws.subscriptions import Subscription, SubscriptionManager
from market_stream.gapfill.rest_gapfill import BitgetRestGapFillWorker
from market_stream.provider_diagnostics import ProviderDiagnostics
from market_stream.normalization.models import NormalizedEvent, extract_sequence
from market_stream.sinks.postgres_raw import PostgresRawSink
from market_stream.sinks.redis_stream import RedisStreamSink

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]
ConnectedCallback = Callable[..., Awaitable[None]]


def _sequence_tracking_key(message: dict[str, Any]) -> str | None:
    """Pro Kanal/Instanz sequenzieren; books* ausgeschlossen (eigenes OB-Protokoll)."""
    arg = message.get("arg")
    if not isinstance(arg, dict):
        return None
    channel = arg.get("channel")
    if channel in (None, "", "books", "books5"):
        return None
    inst_id = str(arg.get("instId") or "")
    return f"{channel}:{inst_id}"


@dataclass(slots=True)
class ClientRuntimeStats:
    ws_mode: str
    started_at_ms: int
    connection_state: str = "stopped"
    active_subscriptions: int = 0
    last_seq: int | None = None
    last_seq_channel_key: str | None = None
    tracked_seq_channels: int = 0
    last_event_ts_ms: int | None = None
    last_exchange_ts_ms: int | None = None
    last_ingest_latency_ms: int | None = None
    gap_events_count: int = 0
    stale_escalation_count: int = 0
    last_ping_ts_ms: int | None = None
    last_pong_ts_ms: int | None = None
    published_events: int = 0
    reconnect_count: int = 0
    last_reconnect_at_ms: int | None = None
    ping_count: int = 0
    pong_count: int = 0
    redis_connected: bool = False
    postgres_connected: bool = False
    last_error: str | None = None


class BitgetPublicWsClient:
    def __init__(
        self,
        *,
        bitget_settings: BitgetSettings,
        rate_limiter: RateLimiter,
        redis_sink: RedisStreamSink,
        postgres_sink: PostgresRawSink,
        gapfill_worker: BitgetRestGapFillWorker,
        stats: ClientRuntimeStats,
        logger: logging.Logger | None = None,
        ws_mode: str = "classic",
        ping_interval_sec: float = 30.0,
        pong_timeout_sec: float = 65.0,
        stale_after_sec: int = 60,
        stale_escalation_max_cycles: int = 12,
        reconnect_initial_delay_sec: float = 1.0,
        reconnect_max_delay_sec: float = 30.0,
        initial_subscriptions: list[Subscription] | None = None,
        message_handlers: list[MessageHandler] | None = None,
        connected_callbacks: list[ConnectedCallback] | None = None,
        provider_diagnostics: ProviderDiagnostics | None = None,
        sequence_gap_buffer_ms: float = 500.0,
    ) -> None:
        self._bitget_settings = bitget_settings
        self._rate_limiter = rate_limiter
        self._redis_sink = redis_sink
        self._postgres_sink = postgres_sink
        self._gapfill_worker = gapfill_worker
        self._stats = stats
        self._logger = logger or logging.getLogger("market_stream.ws")
        self._ws_mode = ws_mode
        self._ping_interval_sec = ping_interval_sec
        self._pong_timeout_sec = pong_timeout_sec
        self._stale_after_sec = stale_after_sec
        self._stale_escalation_max_cycles = max(1, stale_escalation_max_cycles)
        self._reconnect_initial_delay_sec = reconnect_initial_delay_sec
        self._reconnect_max_delay_sec = reconnect_max_delay_sec
        self._subscriptions = SubscriptionManager(max_channels=50)
        self._stop_event = asyncio.Event()
        self._send_lock = asyncio.Lock()
        self._websocket: Any | None = None
        self._last_pong_monotonic = time.monotonic()
        self._last_inbound_monotonic = time.monotonic()
        self._last_stale_gapfill_ts_ms: int | None = None
        self._stale_escalation_count = 0
        self._last_seq_by_key: dict[str, int] = {}
        self._ever_connected = False
        self._message_handlers = message_handlers or []
        self._connected_callbacks = connected_callbacks or []
        self._provider_diagnostics = provider_diagnostics
        self._seq_gap_buffer_ms = float(sequence_gap_buffer_ms)
        self._seq_buffer = BitgetWsSequenceBuffer(
            gap_buffer_ms=self._seq_gap_buffer_ms,
            on_gap_timeout=self._on_sequence_buffer_timeout,
            logger=self._logger,
        )

        for subscription in initial_subscriptions or []:
            self._subscriptions.add(subscription)
        self._stats.active_subscriptions = self._subscriptions.count()

    def subscription_coverage(self) -> list[dict[str, str]]:
        return [sub.to_ws_arg() for sub in self._subscriptions.list()]

    async def run(self) -> None:
        backoff = self._reconnect_initial_delay_sec
        while not self._stop_event.is_set():
            try:
                await self._run_once()
                backoff = self._reconnect_initial_delay_sec
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._stats.last_error = str(exc)
                self._stats.connection_state = "reconnecting"
                self._stats.reconnect_count += 1
                self._stats.last_reconnect_at_ms = int(time.time() * 1000)
                if self._provider_diagnostics is not None:
                    self._provider_diagnostics.record_transport_error(
                        f"ws_reconnect scheduled err={type(exc).__name__}: {exc}"
                    )
                self._logger.warning(
                    "WS reconnect scheduled in %.1fs because of error: %s",
                    backoff,
                    exc,
                )
                if self._stop_event.is_set():
                    break
                jittered = backoff * random.uniform(1.0, 1.25)
                await asyncio.sleep(min(jittered, self._reconnect_max_delay_sec))
                backoff = min(self._reconnect_max_delay_sec, backoff * 2)
        self._stats.connection_state = "stopped"

    async def stop(self) -> None:
        self._stop_event.set()
        if self._websocket is not None:
            await self._websocket.close()

    async def subscribe(self, inst_type: str, channel: str, inst_id: str) -> bool:
        subscription = Subscription(inst_type=inst_type, channel=channel, inst_id=inst_id)
        added = self._subscriptions.add(subscription)
        self._stats.active_subscriptions = self._subscriptions.count()
        if not added:
            return False
        if self._websocket is not None:
            await self._send_json(self._subscriptions.build_subscribe_payload([subscription]))
        return True

    async def unsubscribe(self, inst_type: str, channel: str, inst_id: str) -> bool:
        subscription = Subscription(inst_type=inst_type, channel=channel, inst_id=inst_id)
        removed = self._subscriptions.remove(subscription)
        self._stats.active_subscriptions = self._subscriptions.count()
        if not removed:
            return False
        if self._websocket is not None:
            await self._send_json(
                self._subscriptions.build_unsubscribe_payload([subscription])
            )
        return True

    async def _run_once(self) -> None:
        self._stats.connection_state = "connecting"
        async with websockets.connect(
            self._bitget_settings.effective_ws_public_url,
            ping_interval=None,
            ping_timeout=None,
            close_timeout=5,
            max_queue=1000,
        ) as websocket:
            self._websocket = websocket
            self._last_pong_monotonic = time.monotonic()
            self._last_inbound_monotonic = time.monotonic()
            self._last_seq_by_key.clear()
            self._seq_buffer.clear()
            self._stale_escalation_count = 0
            self._stats.tracked_seq_channels = 0
            self._stats.stale_escalation_count = 0
            self._stats.connection_state = "connected"
            self._stats.last_error = None
            self._logger.info("WS connected")
            await self._resubscribe_all()
            is_reconnect = self._ever_connected
            if self._ever_connected:
                await self._gapfill_worker.on_reconnect()
            for callback in self._connected_callbacks:
                try:
                    await callback(is_reconnect=is_reconnect)
                except Exception as exc:
                    self._logger.warning("connected callback failed: %s", exc)
            self._ever_connected = True

            tasks = [
                asyncio.create_task(self._receive_loop(), name="market-stream-recv"),
                asyncio.create_task(self._ping_loop(), name="market-stream-ping"),
                asyncio.create_task(self._pong_watcher(), name="market-stream-pong"),
                asyncio.create_task(self._stale_data_loop(), name="market-stream-stale"),
            ]
            try:
                done, _pending = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_EXCEPTION,
                )
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                self._websocket = None

            for task in done:
                exception = task.exception()
                if exception is not None:
                    raise exception
            if not self._stop_event.is_set():
                raise RuntimeError("websocket loop ended without exception")

    async def _resubscribe_all(self) -> None:
        subscriptions = self._subscriptions.list()
        if not subscriptions:
            return
        for subscription in subscriptions:
            await self._send_json(self._subscriptions.build_subscribe_payload([subscription]))

    async def _receive_loop(self) -> None:
        if self._websocket is None:
            return
        async for raw_message in self._websocket:
            self._last_inbound_monotonic = time.monotonic()
            text_message = (
                raw_message.decode("utf-8")
                if isinstance(raw_message, bytes)
                else raw_message
            )
            if text_message == "pong":
                self._mark_pong()
                continue

            try:
                decoded = json.loads(text_message)
            except json.JSONDecodeError:
                self._logger.warning("ignoring non-JSON WS frame: %s", text_message)
                continue
            if not isinstance(decoded, dict):
                self._logger.warning("ignoring non-object WS frame")
                continue
            if decoded.get("event") == "pong":
                self._mark_pong()
                continue

            track_key = _sequence_tracking_key(decoded)
            ready = await self._seq_buffer.feed(track_key, decoded)
            if not ready:
                continue

            for item in ready:
                event = NormalizedEvent.from_ws_message(item)
                self._stats.last_event_ts_ms = event.ingest_ts_ms
                canon = event.to_canonical(gap_flag=False)
                lat = canon.approx_latency_ms()
                if lat is not None:
                    self._stats.last_ingest_latency_ms = lat
                if event.exchange_ts_ms is not None:
                    self._stats.last_exchange_ts_ms = int(event.exchange_ts_ms)
                self._stale_escalation_count = 0
                self._stats.stale_escalation_count = 0
                self._handle_subscription_ack(item)
                k2 = _sequence_tracking_key(item)
                self._update_seq_published_stats(k2, item)
                await self._publish_event(event)
                for handler in self._message_handlers:
                    try:
                        await handler(item)
                    except Exception as exc:
                        self._logger.warning("message handler failed: %s", exc)

    async def _ping_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(self._ping_interval_sec)
            await self._send_text("ping")
            self._stats.ping_count += 1
            self._stats.last_ping_ts_ms = int(time.time() * 1000)
            self._logger.info("WS ping sent")

    async def _pong_watcher(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            last_heartbeat = max(self._last_pong_monotonic, self._last_inbound_monotonic)
            if time.monotonic() - last_heartbeat > self._pong_timeout_sec:
                raise TimeoutError("WS pong timeout")

    async def _stale_data_loop(self) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            last_event_ts_ms = self._stats.last_event_ts_ms
            if last_event_ts_ms is None:
                continue
            now_ms = int(time.time() * 1000)
            stale_for_ms = now_ms - last_event_ts_ms
            if stale_for_ms < self._stale_after_sec * 1000:
                self._stale_escalation_count = 0
                self._stats.stale_escalation_count = 0
                continue
            self._stale_escalation_count += 1
            self._stats.stale_escalation_count = self._stale_escalation_count
            if self._stale_escalation_count >= self._stale_escalation_max_cycles:
                self._logger.error(
                    "market feed stale escalation cycles=%s — forcing ws reconnect",
                    self._stale_escalation_count,
                )
                raise RuntimeError("market feed stale escalation")
            if (
                self._last_stale_gapfill_ts_ms is not None
                and now_ms - self._last_stale_gapfill_ts_ms < self._stale_after_sec * 1000
            ):
                continue
            self._last_stale_gapfill_ts_ms = now_ms
            self._logger.warning(
                "stale market data detected (escalation=%s), triggering gap-fill",
                self._stale_escalation_count,
            )
            await self._gapfill_worker.maybe_gapfill_if_stale(
                last_event_ts_ms=last_event_ts_ms,
                stale_after_sec=self._stale_after_sec,
            )

    async def _send_json(self, payload: dict[str, object]) -> None:
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")
        async with self._send_lock:
            await self._rate_limiter.acquire()
            await self._websocket.send(json.dumps(payload, separators=(",", ":")))

    async def _send_text(self, payload: str) -> None:
        if self._websocket is None:
            raise RuntimeError("WebSocket not connected")
        async with self._send_lock:
            await self._rate_limiter.acquire()
            await self._websocket.send(payload)

    def _mark_pong(self) -> None:
        self._last_pong_monotonic = time.monotonic()
        self._stats.pong_count += 1
        self._stats.last_pong_ts_ms = int(time.time() * 1000)
        self._logger.info("WS pong received")

    def _update_seq_published_stats(
        self, key: str | None, message: dict[str, Any]
    ) -> None:
        if key is None:
            return
        current_seq = extract_sequence(message)
        if current_seq is None:
            return
        self._last_seq_by_key[key] = current_seq
        self._stats.last_seq = current_seq
        self._stats.last_seq_channel_key = key
        self._stats.tracked_seq_channels = len(self._last_seq_by_key)

    async def _on_sequence_buffer_timeout(self, key: str, lost_ticks: int) -> None:
        sym = key.rsplit(":", 1)[-1] if ":" in key else None
        self._logger.critical(
            "CRITICAL_WARNING: market stream sequence gap unresolved after %.0fms key=%s "
            "lost_ticks=%s — STREAM_GAP_EVENT",
            self._seq_gap_buffer_ms,
            key,
            lost_ticks,
            extra=provider_log_extra(
                provider="bitget_ws",
                event="STREAM_GAP_EVENT",
                symbol=sym,
            ),
        )
        self._stats.gap_events_count += 1
        if self._provider_diagnostics is not None:
            self._provider_diagnostics.record_transport_error(
                f"STREAM_GAP_EVENT key={key} lost_ticks={lost_ticks}"
            )
        await self._gapfill_worker.on_gap_detected(
            reason=f"STREAM_GAP_EVENT:seq-timeout:{key}:lost={lost_ticks}"
        )
        if self._websocket is not None:
            with contextlib.suppress(Exception):
                await self._websocket.close()

    def _handle_subscription_ack(self, message: dict[str, Any]) -> None:
        event_name = message.get("event")
        if not isinstance(event_name, str):
            return
        if event_name == "subscribe":
            arg = message.get("arg") if isinstance(message.get("arg"), dict) else {}
            channel = arg.get("channel", "unknown")
            inst_id = arg.get("instId", self._bitget_settings.symbol)
            self._logger.info("subscribed %s %s", channel, inst_id)
        elif event_name == "error":
            self._logger.warning("Bitget WS error event: %s", message)
            if self._provider_diagnostics is not None:
                try:
                    detail = json.dumps(message, ensure_ascii=False)[:2000]
                except (TypeError, ValueError):
                    detail = str(message)[:2000]
                self._provider_diagnostics.record_protocol_error("bitget_ws_error", detail)

    async def _publish_event(self, event: NormalizedEvent) -> None:
        redis_id = await self._redis_sink.publish(event)
        postgres_inserted = await self._postgres_sink.insert(event)
        self._stats.redis_connected = self._redis_sink.is_connected
        self._stats.postgres_connected = self._postgres_sink.is_connected
        if redis_id is not None or postgres_inserted:
            self._stats.published_events += 1
            self._logger.info(
                "Events published channel=%s inst_id=%s action=%s",
                event.channel,
                event.inst_id,
                event.action,
            )
        elif redis_id is None and not postgres_inserted:
            with contextlib.suppress(Exception):
                if self._postgres_sink.raw_persist_enabled:
                    inc_pipeline_event_drop(
                        component="bitget_public_ws",
                        reason="dual_sink_failure",
                    )
                else:
                    inc_pipeline_event_drop(
                        component="bitget_public_ws",
                        reason="redis_raw_publish_failed",
                    )
