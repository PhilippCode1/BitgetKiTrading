from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

from redis.exceptions import RedisError
from shared_py.observability.metrics import inc_pipeline_event_drop

from shared_py.eventbus import (
    EventEnvelope,
    RedisStreamBus,
    SharedMemoryBus,
    make_stream_bus_from_url,
)


class AsyncRedisEventBus:
    def __init__(
        self,
        redis_url: str,
        *,
        dedupe_ttl_sec: int = 0,
        default_block_ms: int = 2000,
        default_count: int = 50,
        logger: logging.Logger | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._dedupe_ttl_sec = dedupe_ttl_sec
        self._default_block_ms = default_block_ms
        self._default_count = default_count
        self._logger = logger or logging.getLogger("market_stream.eventbus")
        self._bus: RedisStreamBus | SharedMemoryBus | None = None
        self._last_connect_attempt_monotonic = 0.0
        self._retry_cooldown_sec = 5.0

    @property
    def is_connected(self) -> bool:
        return self._bus is not None

    async def connect(self) -> bool:
        if self._bus is not None:
            return True
        now = time.monotonic()
        if now - self._last_connect_attempt_monotonic < self._retry_cooldown_sec:
            return False
        self._last_connect_attempt_monotonic = now
        try:
            self._bus = await asyncio.to_thread(self._connect_sync)
        except (OSError, RedisError) as exc:
            self._logger.warning("EventBus connect failed: %s", exc)
            self._bus = None
            return False
        self._logger.info("EventBus publisher connected")
        return True

    async def publish(self, stream: str, envelope: EventEnvelope) -> str | None:
        if not await self.connect():
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream_eventbus",
                    reason="eventbus_unavailable",
                )
            return None
        if self._bus is None:
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream_eventbus",
                    reason="eventbus_unavailable",
                )
            return None
        try:
            return await asyncio.to_thread(self._bus.publish, stream, envelope)
        except (OSError, RedisError, ValueError) as exc:
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream_eventbus",
                    reason="eventbus_publish_failed",
                )
            self._logger.warning("EventBus publish failed stream=%s error=%s", stream, exc)
            await self.close()
            return None

    async def publish_dlq(
        self,
        original: EventEnvelope | dict[str, Any] | Any,
        error_info: dict[str, Any],
    ) -> str | None:
        if not await self.connect():
            return None
        if self._bus is None:
            return None
        try:
            return await asyncio.to_thread(self._bus.publish_dlq, original, error_info)
        except (OSError, RedisError, ValueError) as exc:
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream_eventbus",
                    reason="eventbus_dlq_failed",
                )
            self._logger.warning("EventBus DLQ publish failed: %s", exc)
            await self.close()
            return None

    async def close(self) -> None:
        if self._bus is None:
            return
        bus = self._bus
        self._bus = None
        await asyncio.to_thread(bus.close)

    def _connect_sync(self) -> RedisStreamBus | SharedMemoryBus:
        bus = make_stream_bus_from_url(
            self._redis_url,
            dedupe_ttl_sec=self._dedupe_ttl_sec,
            default_block_ms=self._default_block_ms,
            default_count=self._default_count,
            logger=self._logger,
        )
        bus.ping()
        return bus
