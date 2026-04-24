from __future__ import annotations

import json
import logging
import time
import uuid

import asyncpg
from asyncpg import Pool

from market_stream.normalization.models import NormalizedEvent

INSERT_RAW_EVENT_SQL = """
INSERT INTO raw_events (
    id,
    source,
    inst_type,
    channel,
    inst_id,
    action,
    exchange_ts_ms,
    ingest_ts_ms,
    payload
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
"""


class PostgresRawSink:
    def __init__(
        self,
        database_url: str,
        *,
        enabled: bool,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database_url = database_url
        self._enabled = enabled
        self._pool: Pool | None = None
        self._logger = logger or logging.getLogger("market_stream.postgres")
        self._last_connect_attempt_monotonic = 0.0
        self._retry_cooldown_sec = 5.0

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    @property
    def raw_persist_enabled(self) -> bool:
        return self._enabled

    async def connect(self) -> bool:
        if not self._enabled:
            return False
        if self._pool is not None:
            return True
        now = time.monotonic()
        if now - self._last_connect_attempt_monotonic < self._retry_cooldown_sec:
            return False
        self._last_connect_attempt_monotonic = now
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._database_url,
                min_size=1,
                max_size=2,
            )
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("Postgres connect failed: %s", exc)
            self._pool = None
            return False
        self._logger.info("Postgres raw sink connected")
        return True

    async def insert(self, event: NormalizedEvent) -> bool:
        if not self._enabled:
            return False
        if not await self.connect():
            return False
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as connection:
                await connection.execute(
                    INSERT_RAW_EVENT_SQL,
                    uuid.UUID(event.event_id),
                    event.source,
                    event.inst_type,
                    event.channel,
                    event.inst_id,
                    event.action,
                    event.exchange_ts_ms,
                    event.ingest_ts_ms,
                    json.dumps(event.payload),
                )
        except (ValueError, OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("raw_events insert failed: %s", exc)
            return False
        return True

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
