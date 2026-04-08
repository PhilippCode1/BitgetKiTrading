from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

import asyncpg
from asyncpg import Pool

if TYPE_CHECKING:
    from market_stream.collectors.orderbook import OrderBookPersistSnapshot

INSERT_ORDERBOOK_SNAPSHOT_SQL = """
INSERT INTO tsdb.orderbook_top25 (
    symbol,
    ts_ms,
    seq,
    checksum,
    bids_raw,
    asks_raw,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
ON CONFLICT (symbol, ts_ms)
DO UPDATE SET
    seq = EXCLUDED.seq,
    checksum = EXCLUDED.checksum,
    bids_raw = EXCLUDED.bids_raw,
    asks_raw = EXCLUDED.asks_raw,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""

INSERT_ORDERBOOK_LEVEL_SQL = """
INSERT INTO tsdb.orderbook_levels (
    symbol,
    ts_ms,
    side,
    level,
    price,
    size,
    ingest_ts_ms
) VALUES ($1, $2, $3, $4, $5, $6, $7)
ON CONFLICT (symbol, ts_ms, side, level)
DO UPDATE SET
    price = EXCLUDED.price,
    size = EXCLUDED.size,
    ingest_ts_ms = EXCLUDED.ingest_ts_ms
"""


class OrderBookRepository:
    def __init__(
        self,
        database_url: str,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._database_url = database_url
        self._pool: Pool | None = None
        self._logger = logger or logging.getLogger("market_stream.orderbook_repo")
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
            self._logger.warning("Orderbook repo connect failed: %s", exc)
            self._pool = None
            return False
        self._logger.info("Orderbook repository connected")
        return True

    async def insert_snapshot(self, snapshot: OrderBookPersistSnapshot) -> bool:
        if not await self.connect():
            return False
        if self._pool is None:
            return False

        ingest_ts_ms = int(time.time() * 1000)
        level_rows = _build_level_rows(snapshot)
        try:
            async with self._pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        INSERT_ORDERBOOK_SNAPSHOT_SQL,
                        snapshot.symbol,
                        snapshot.ts_ms,
                        snapshot.seq,
                        snapshot.checksum,
                        json.dumps(
                            [[price, size] for price, size in snapshot.bids[:25]],
                            separators=(",", ":"),
                        ),
                        json.dumps(
                            [[price, size] for price, size in snapshot.asks[:25]],
                            separators=(",", ":"),
                        ),
                        ingest_ts_ms,
                    )
                    if level_rows:
                        await connection.executemany(INSERT_ORDERBOOK_LEVEL_SQL, level_rows)
        except (InvalidOperation, ValueError, OSError, asyncpg.PostgresError) as exc:
            self._logger.warning("orderbook snapshot insert failed: %s", exc)
            return False
        return True

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None


def _build_level_rows(
    snapshot: OrderBookPersistSnapshot,
) -> Sequence[tuple[str, int, str, int, Decimal, Decimal, int]]:
    ingest_ts_ms = int(time.time() * 1000)
    rows: list[tuple[str, int, str, int, Decimal, Decimal, int]] = []
    for side, levels in (("bid", snapshot.bids), ("ask", snapshot.asks)):
        for index, (price, size) in enumerate(levels, start=1):
            rows.append(
                (
                    snapshot.symbol,
                    snapshot.ts_ms,
                    side,
                    index,
                    Decimal(price),
                    Decimal(size),
                    ingest_ts_ms,
                )
            )
    return rows
