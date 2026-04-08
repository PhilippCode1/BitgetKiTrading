from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg


def insert_fill(
    conn: psycopg.Connection[Any],
    *,
    order_id: UUID,
    position_id: UUID,
    ts_ms: int,
    price: Decimal,
    qty_base: Decimal,
    liquidity: str,
    fee_usdt: Decimal,
    notional_usdt: Decimal,
) -> UUID:
    fid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.fills (
            fill_id, order_id, position_id, ts_ms, price, qty_base, liquidity, fee_usdt, notional_usdt
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            str(fid),
            str(order_id),
            str(position_id),
            ts_ms,
            str(price),
            str(qty_base),
            liquidity,
            str(fee_usdt),
            str(notional_usdt),
        ),
    )
    return fid


def insert_fee_ledger(
    conn: psycopg.Connection[Any],
    *,
    position_id: UUID,
    ts_ms: int,
    fee_usdt: Decimal,
    reason: str,
) -> UUID:
    eid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.fee_ledger (fee_id, position_id, ts_ms, fee_usdt, reason)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (str(eid), str(position_id), ts_ms, str(fee_usdt), reason),
    )
    return eid


def insert_funding_ledger(
    conn: psycopg.Connection[Any],
    *,
    position_id: UUID,
    ts_ms: int,
    funding_rate: Decimal,
    position_value_usdt: Decimal,
    funding_usdt: Decimal,
    source: str,
) -> UUID:
    uid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.funding_ledger (
            funding_id, position_id, ts_ms, funding_rate, position_value_usdt, funding_usdt, source
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            str(uid),
            str(position_id),
            ts_ms,
            str(funding_rate),
            str(position_value_usdt),
            str(funding_usdt),
            source,
        ),
    )
    return uid


def sum_fees_for_position(conn: psycopg.Connection[Any], position_id: UUID) -> Decimal:
    row = conn.execute(
        "SELECT COALESCE(SUM(fee_usdt), 0) FROM paper.fee_ledger WHERE position_id = %s",
        (str(position_id),),
    ).fetchone()
    return Decimal(str(row[0])) if row else Decimal("0")


def sum_funding_for_position(conn: psycopg.Connection[Any], position_id: UUID) -> Decimal:
    """Summe gebuchter Funding-Betraege (positiv = erhalten, negativ = gezahlt)."""
    row = conn.execute(
        "SELECT COALESCE(SUM(funding_usdt), 0) FROM paper.funding_ledger WHERE position_id = %s",
        (str(position_id),),
    ).fetchone()
    return Decimal(str(row[0])) if row else Decimal("0")
