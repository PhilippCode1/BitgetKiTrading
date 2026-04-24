from __future__ import annotations

import contextlib
import json
import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError
from shared_py.observability.metrics import inc_pipeline_event_drop, set_pipeline_backpressure_queue_size

from market_stream.normalization.models import NormalizedEvent


class RedisStreamSink:
    def __init__(
        self,
        redis_url: str,
        *,
        stream_key: str = "stream:market:raw",
        maxlen: int | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._stream_key = stream_key
        self._maxlen = maxlen
        self._redis: Redis | None = None
        self._logger = logger or logging.getLogger("market_stream.redis")
        self._last_connect_attempt_monotonic = 0.0
        self._retry_cooldown_sec = 5.0

    @property
    def stream_key(self) -> str:
        return self._stream_key

    @property
    def is_connected(self) -> bool:
        return self._redis is not None

    async def connect(self) -> bool:
        if self._redis is not None:
            return True
        now = time.monotonic()
        if now - self._last_connect_attempt_monotonic < self._retry_cooldown_sec:
            return False
        self._last_connect_attempt_monotonic = now
        try:
            redis_client = Redis.from_url(self._redis_url, decode_responses=True)
            await redis_client.ping()
        except (OSError, RedisError) as exc:
            self._logger.warning("Redis connect failed: %s", exc)
            return False
        self._redis = redis_client
        self._logger.info("Redis stream sink connected")
        return True

    async def publish(self, event: NormalizedEvent) -> str | None:
        if not await self.connect():
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream",
                    reason="redis_sink_unreachable",
                )
            return None
        if self._redis is None:
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream",
                    reason="redis_sink_unreachable",
                )
            return None

        fields: dict[str, str] = {
            "event_id": event.event_id,
            "source": event.source,
            "inst_type": event.inst_type or "",
            "channel": event.channel or "",
            "inst_id": event.inst_id or "",
            "action": event.action,
            "exchange_ts_ms": "" if event.exchange_ts_ms is None else str(event.exchange_ts_ms),
            "ingest_ts_ms": str(event.ingest_ts_ms),
            "payload": json.dumps(event.payload, separators=(",", ":"), sort_keys=True),
        }
        try:
            kwargs: dict[str, object] = {}
            if self._maxlen is not None:
                kwargs["maxlen"] = self._maxlen
                kwargs["approximate"] = True
            new_id = await self._redis.xadd(self._stream_key, fields, **kwargs)
            with contextlib.suppress(Exception):
                n = int(await self._redis.xlen(self._stream_key))
                set_pipeline_backpressure_queue_size(stream=self._stream_key, size=n)
            return new_id
        except (OSError, RedisError) as exc:
            with contextlib.suppress(Exception):
                inc_pipeline_event_drop(
                    component="market_stream",
                    reason="redis_xadd_failed",
                )
            self._logger.warning("Redis XADD failed: %s", exc)
            await self.close()
            return None

    async def set_json(
        self,
        key: str,
        data: object,
        *,
        ex_sec: int = 120,
    ) -> bool:
        """Kurzlebiger Snapshot (z. B. Orderbook Top-5) fuer pre-flight liquidity guard."""
        if not key or not key.strip():
            return False
        if not await self.connect():
            return False
        if self._redis is None:
            return False
        try:
            ex = int(ex_sec) if ex_sec and ex_sec > 0 else None
            if ex is not None and ex < 1:
                ex = None
            s = json.dumps(
                data,
                separators=(",", ":"),
                default=str,
            )
            if ex is not None:
                await self._redis.set(name=key, value=s, ex=ex)
            else:
                await self._redis.set(name=key, value=s)
            return True
        except (OSError, RedisError, TypeError) as exc:
            self._logger.debug("redis SET failed key=%s: %s", key, exc)
            return False

    async def set_key_with_ttl(
        self,
        key: str,
        value: str,
        *,
        ex_sec: int,
    ) -> bool:
        """
        Einfaches SET mit Ablauf (z. B. market:locked:[symbol] waehrend Orderbook-Resync).
        """
        if not key or not key.strip():
            return False
        if not await self.connect():
            return False
        if self._redis is None:
            return False
        try:
            ex = max(1, int(ex_sec))
            await self._redis.set(name=key, value=value, ex=ex)
            return True
        except (OSError, RedisError, TypeError) as exc:
            self._logger.debug("redis SET (ttl) failed key=%s: %s", key, exc)
            return False

    async def close(self) -> None:
        if self._redis is None:
            return
        await self._redis.close()
        self._redis = None
