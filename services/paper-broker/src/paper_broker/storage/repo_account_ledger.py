from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg


def insert_entry(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    ts_ms: int,
    amount_usdt: Decimal,
    balance_after: Decimal,
    reason: str,
    note: str | None = None,
    meta: dict[str, Any] | None = None,
) -> UUID:
    eid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.account_ledger (
            entry_id, account_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            str(eid),
            str(account_id),
            ts_ms,
            str(amount_usdt),
            str(balance_after),
            reason,
            note,
            json.dumps(meta or {}, separators=(",", ":"), ensure_ascii=False),
        ),
    )
    return eid


def insert_bootstrap(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    ts_ms: int,
    initial_equity: Decimal,
) -> UUID:
    return insert_entry(
        conn,
        account_id=account_id,
        ts_ms=ts_ms,
        amount_usdt=initial_equity,
        balance_after=initial_equity,
        reason="bootstrap",
        note="paper account created",
        meta={},
    )
