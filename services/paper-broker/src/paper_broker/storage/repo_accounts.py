from __future__ import annotations

import time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg

from paper_broker.storage import repo_account_ledger


def bootstrap_account(
    conn: psycopg.Connection[Any],
    *,
    initial_equity: Decimal,
) -> UUID:
    aid = uuid4()
    ts_ms = int(time.time() * 1000)
    conn.execute(
        """
        INSERT INTO paper.accounts (account_id, initial_equity, equity)
        VALUES (%s, %s, %s)
        """,
        (str(aid), str(initial_equity), str(initial_equity)),
    )
    repo_account_ledger.insert_bootstrap(
        conn,
        account_id=aid,
        ts_ms=ts_ms,
        initial_equity=initial_equity,
    )
    return aid


def first_account_id(conn: psycopg.Connection[Any]) -> UUID | None:
    row = conn.execute(
        "SELECT account_id FROM paper.accounts ORDER BY account_id ASC LIMIT 1"
    ).fetchone()
    return UUID(str(row["account_id"])) if row else None


def get_account(
    conn: psycopg.Connection[Any],
    account_id: UUID,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM paper.accounts WHERE account_id = %s",
        (str(account_id),),
    ).fetchone()
    return dict(row) if row else None


def update_account_equity(
    conn: psycopg.Connection[Any],
    account_id: UUID,
    equity: Decimal,
) -> None:
    conn.execute(
        "UPDATE paper.accounts SET equity = %s WHERE account_id = %s",
        (str(equity), str(account_id)),
    )
