from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

import asyncpg
from asyncpg import Pool

if TYPE_CHECKING:
    from market_stream.collectors.trades import TradeRecord

UPSERT_TRADES_SQL = """
INSERT INTO tsdb.trades (
    symbol,
    trade_id,
    ts_ms,
    price,
    size,
    side,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (symbol, trade_id)
DO UPDATE SET
    ts_ms = EXCLUDED.ts_ms,
    price = EXCLUDED.price,
    size = EXCLUDED.size,
    side = EXCLUDED.side,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""


class TradesRepository:
    def __init__(
        self,
        database_url: str,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: Pool | None = None
        self._logger = logger or logging.getLogger("market_stream.trades_repo")
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
            self._logger.warning("Trades repo connect failed: %s", exc)
            self._pool = None
            return False
        self._logger.info("Trades repository connected")
        return True

    async def upsert_trades(self, trades: Sequence[TradeRecord]) -> int:
        if not trades:
            return 0
        if not await self.connect():
            return 0
        if self._pool is None:
            return 0

        rows = [
            (
                trade.symbol,
                trade.trade_id,
                trade.ts_ms,
                trade.price,
                trade.size,
                trade.side,
                trade.ingest_ts_ms,
            )
            for trade in trades
        ]
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.executemany(UPSERT_TRADES_SQL, rows)
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("trade upsert failed: %s", exc)
            return 0
        return len(rows)

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None
