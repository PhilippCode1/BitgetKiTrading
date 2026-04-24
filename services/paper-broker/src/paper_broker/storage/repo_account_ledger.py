from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg

from paper_broker.exceptions import InsufficientPaperFundsException


def _dec_ledger(x: object, d: str = "0") -> Decimal:
    if x in (None, ""):
        return Decimal(d)
    return Decimal(str(x))


def assert_sufficient_paper_cash(
    *,
    available_cash_usdt: Decimal,
    initial_margin_usdt: Decimal,
    order_fee_usdt: Decimal = Decimal("0"),
) -> None:
    """
    available_cash_usdt: freie Kontoquote (kein locked margin);
    initial_margin: Order-Initialmarge; order_fee: Entry-Gebuehr in USDT.
    """
    a = _dec_ledger(available_cash_usdt, "0")
    m = _dec_ledger(initial_margin_usdt, "0")
    f = _dec_ledger(order_fee_usdt, "0")
    if a < m + f:
        raise InsufficientPaperFundsException(
            "insufficient_paper_funds",
            available_usdt=a,
            required_usdt=m + f,
        )


def insert_entry(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    tenant_id: str,
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
            entry_id, account_id, tenant_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
        """,
        (
            str(eid),
            str(account_id),
            str(tenant_id).strip() or "default",
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
    tenant_id: str,
    ts_ms: int,
    initial_equity: Decimal,
) -> UUID:
    return insert_entry(
        conn,
        account_id=account_id,
        tenant_id=tenant_id,
        ts_ms=ts_ms,
        amount_usdt=initial_equity,
        balance_after=initial_equity,
        reason="bootstrap",
        note="paper account created",
        meta={},
    )
