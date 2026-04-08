from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg


def insert_order(
    conn: psycopg.Connection[Any],
    *,
    position_id: UUID,
    otype: str,
    side: str,
    qty_base: Decimal,
    limit_price: Decimal | None,
    state: str,
    created_ts_ms: int,
    filled_ts_ms: int | None,
) -> UUID:
    oid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.orders (
            order_id, position_id, type, side, qty_base, limit_price, state, created_ts_ms, filled_ts_ms
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            str(oid),
            str(position_id),
            otype,
            side,
            str(qty_base),
            str(limit_price) if limit_price is not None else None,
            state,
            created_ts_ms,
            filled_ts_ms,
        ),
    )
    return oid


def mark_order_filled(conn: psycopg.Connection[Any], order_id: UUID, filled_ts_ms: int) -> None:
    conn.execute(
        "UPDATE paper.orders SET state = 'filled', filled_ts_ms = %s WHERE order_id = %s",
        (filled_ts_ms, str(order_id)),
    )
