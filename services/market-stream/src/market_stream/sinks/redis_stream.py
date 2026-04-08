from __future__ import annotations

import json
import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

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
            return None
        if self._redis is None:
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
            return await self._redis.xadd(self._stream_key, fields, **kwargs)
        except (OSError, RedisError) as exc:
            self._logger.warning("Redis XADD failed: %s", exc)
            await self.close()
            return None

    async def close(self) -> None:
        if self._redis is None:
            return
        await self._redis.close()
        self._redis = None
