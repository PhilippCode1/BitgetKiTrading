from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

import asyncpg
from asyncpg import Pool

if TYPE_CHECKING:
    from market_stream.collectors.candles import Candle

UPSERT_CANDLE_SQL = """
INSERT INTO tsdb.candles (
    symbol,
    timeframe,
    start_ts_ms,
    open,
    high,
    low,
    close,
    base_vol,
    quote_vol,
    usdt_vol,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
ON CONFLICT (symbol, timeframe, start_ts_ms)
DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    base_vol = EXCLUDED.base_vol,
    quote_vol = EXCLUDED.quote_vol,
    usdt_vol = EXCLUDED.usdt_vol,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""

DELETE_OLD_CANDLES_SQL = """
DELETE FROM tsdb.candles
WHERE symbol = $1
  AND timeframe = $2
  AND start_ts_ms < $3
"""


class CandlesRepository:
    def __init__(
        self,
        database_url: str,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: Pool | None = None
        self._logger = logger or logging.getLogger("market_stream.candles_repo")
        self._last_connect_attempt_monotonic = 0.0
        self._retry_cooldown_sec = 5.0

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    async def connect(self) -> bool:
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
                max_size=4,
            )
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("Candles repo connect failed: %s", exc)
            self._pool = None
            return False
        self._logger.info("Candles repository connected")
        return True

    async def upsert_candles(self, candles: Sequence[Candle]) -> int:
        if not candles:
            return 0
        if not await self.connect():
            return 0
        if self._pool is None:
            return 0

        rows = [
            (
                candle.symbol,
                candle.timeframe,
                candle.start_ts_ms,
                candle.o,
                candle.h,
                candle.l,
                candle.c,
                candle.base_vol,
                candle.quote_vol,
                candle.usdt_vol,
                int(time.time() * 1000),
            )
            for candle in candles
        ]
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.executemany(UPSERT_CANDLE_SQL, rows)
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("candle upsert failed: %s", exc)
            return 0
        return len(rows)

    async def delete_older_than(
        self,
        *,
        symbol: str,
        timeframe: str,
        cutoff_ts_ms: int,
    ) -> int:
        if not await self.connect():
            return 0
        if self._pool is None:
            return 0
        try:
            async with self._pool.acquire() as connection:
                result = await connection.execute(
                    DELETE_OLD_CANDLES_SQL,
                    symbol,
                    timeframe,
                    cutoff_ts_ms,
                )
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("candle retention delete failed: %s", exc)
            return 0
        deleted_rows = int(result.split()[-1])
        return deleted_rows

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
