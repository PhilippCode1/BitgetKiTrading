from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING

import asyncpg
from asyncpg import Pool

if TYPE_CHECKING:
    from market_stream.collectors.ticker import TickerSnapshot

UPSERT_TICKER_SQL = """
INSERT INTO tsdb.ticker (
    symbol,
    ts_ms,
    source,
    last_pr,
    bid_pr,
    ask_pr,
    bid_sz,
    ask_sz,
    mark_price,
    index_price,
    funding_rate,
    next_funding_time_ms,
    holding_amount,
    base_volume,
    quote_volume,
    funding_rate_interval,
    funding_next_update_ms,
    funding_min_rate,
    funding_max_rate,
    ingest_ts_ms
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
)
ON CONFLICT (symbol, ts_ms)
DO UPDATE SET
    source = EXCLUDED.source,
    last_pr = EXCLUDED.last_pr,
    bid_pr = EXCLUDED.bid_pr,
    ask_pr = EXCLUDED.ask_pr,
    bid_sz = EXCLUDED.bid_sz,
    ask_sz = EXCLUDED.ask_sz,
    mark_price = EXCLUDED.mark_price,
    index_price = EXCLUDED.index_price,
    funding_rate = EXCLUDED.funding_rate,
    next_funding_time_ms = EXCLUDED.next_funding_time_ms,
    holding_amount = EXCLUDED.holding_amount,
    base_volume = EXCLUDED.base_volume,
    quote_volume = EXCLUDED.quote_volume,
    funding_rate_interval = EXCLUDED.funding_rate_interval,
    funding_next_update_ms = EXCLUDED.funding_next_update_ms,
    funding_min_rate = EXCLUDED.funding_min_rate,
    funding_max_rate = EXCLUDED.funding_max_rate,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""

UPSERT_FUNDING_RATE_SQL = """
INSERT INTO tsdb.funding_rate (
    symbol,
    ts_ms,
    source,
    funding_rate,
    interval_hours,
    next_update_ms,
    min_rate,
    max_rate,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
ON CONFLICT (symbol, ts_ms)
DO UPDATE SET
    source = EXCLUDED.source,
    funding_rate = EXCLUDED.funding_rate,
    interval_hours = EXCLUDED.interval_hours,
    next_update_ms = EXCLUDED.next_update_ms,
    min_rate = EXCLUDED.min_rate,
    max_rate = EXCLUDED.max_rate,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""

UPSERT_OPEN_INTEREST_SQL = """
INSERT INTO tsdb.open_interest (
    symbol,
    ts_ms,
    source,
    size,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (symbol, ts_ms)
DO UPDATE SET
    source = EXCLUDED.source,
    size = EXCLUDED.size,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""


class TickerRepository:
    def __init__(
        self,
        database_url: str,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: Pool | None = None
        self._logger = logger or logging.getLogger("market_stream.ticker_repo")
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
            self._logger.warning("Ticker repo connect failed: %s", exc)
            self._pool = None
            return False
        self._logger.info("Ticker repository connected")
        return True

    async def upsert_snapshots(self, snapshots: Sequence[TickerSnapshot]) -> int:
        if not snapshots:
            return 0
        if not await self.connect():
            return 0
        if self._pool is None:
            return 0

        rows = [
            (
                snapshot.symbol,
                snapshot.ts_ms,
                snapshot.source,
                snapshot.last_pr,
                snapshot.bid_pr,
                snapshot.ask_pr,
                snapshot.bid_sz,
                snapshot.ask_sz,
                snapshot.mark_price,
                snapshot.index_price,
                snapshot.funding_rate,
                snapshot.next_funding_time_ms,
                snapshot.holding_amount,
                snapshot.base_volume,
                snapshot.quote_volume,
                snapshot.funding_rate_interval,
                snapshot.funding_next_update_ms,
                snapshot.funding_min_rate,
                snapshot.funding_max_rate,
                snapshot.ingest_ts_ms,
            )
            for snapshot in snapshots
        ]
        funding_rows = [
            (
                snapshot.symbol,
                snapshot.ts_ms,
                snapshot.source,
                snapshot.funding_rate,
                _parse_interval_hours(snapshot.funding_rate_interval),
                snapshot.funding_next_update_ms or snapshot.next_funding_time_ms,
                snapshot.funding_min_rate,
                snapshot.funding_max_rate,
                snapshot.ingest_ts_ms,
            )
            for snapshot in snapshots
            if snapshot.funding_rate is not None
        ]
        open_interest_rows = [
            (
                snapshot.symbol,
                snapshot.ts_ms,
                snapshot.source,
                snapshot.holding_amount,
                snapshot.ingest_ts_ms,
            )
            for snapshot in snapshots
            if snapshot.holding_amount is not None
        ]
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.executemany(UPSERT_TICKER_SQL, rows)
                    if funding_rows:
                        await connection.executemany(UPSERT_FUNDING_RATE_SQL, funding_rows)
                    if open_interest_rows:
                        await connection.executemany(
                            UPSERT_OPEN_INTEREST_SQL,
                            open_interest_rows,
                        )
        except (OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("ticker upsert failed: %s", exc)
            return 0
        return len(rows)

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None


def _parse_interval_hours(value: str | None) -> int | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None
