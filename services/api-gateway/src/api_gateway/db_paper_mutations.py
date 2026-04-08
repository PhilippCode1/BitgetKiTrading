from __future__ import annotations

import json
import time
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg


def resolve_primary_paper_account_id(conn: psycopg.Connection[Any]) -> UUID | None:
    row = conn.execute(
        """
        SELECT account_id FROM paper.accounts
        ORDER BY created_ts ASC NULLS LAST, account_id ASC
        LIMIT 1
        """
    ).fetchone()
    return UUID(str(row["account_id"])) if row else None


def paper_account_deposit_demo(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    amount_usdt: Decimal,
    note: str | None,
) -> dict[str, Any]:
    if amount_usdt == 0:
        raise ValueError("amount_usdt must be non-zero")
    acc = conn.execute(
        "SELECT equity FROM paper.accounts WHERE account_id = %s FOR UPDATE",
        (str(account_id),),
    ).fetchone()
    if not acc:
        raise ValueError("account not found")
    cur = Decimal(str(dict(acc)["equity"]))
    nxt = cur + amount_usdt
    if nxt < 0:
        raise ValueError("insufficient equity for withdrawal")
    ts_ms = int(time.time() * 1000)
    reason = "deposit_demo" if amount_usdt > 0 else "withdraw_demo"
    conn.execute(
        """
        INSERT INTO paper.account_ledger (
            entry_id, account_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        ) VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, '{}'::jsonb)
        """,
        (str(account_id), ts_ms, str(amount_usdt), str(nxt), reason, note),
    )
    conn.execute(
        "UPDATE paper.accounts SET equity = %s WHERE account_id = %s",
        (str(nxt), str(account_id)),
    )
    return {"account_id": str(account_id), "equity_after": str(nxt), "ts_ms": ts_ms}


def paper_account_admin_adjustment(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    delta_usdt: Decimal,
    note: str | None,
) -> dict[str, Any]:
    if delta_usdt == 0:
        raise ValueError("delta_usdt must be non-zero")
    acc = conn.execute(
        "SELECT equity FROM paper.accounts WHERE account_id = %s FOR UPDATE",
        (str(account_id),),
    ).fetchone()
    if not acc:
        raise ValueError("account not found")
    cur = Decimal(str(dict(acc)["equity"]))
    nxt = cur + delta_usdt
    if nxt < 0:
        raise ValueError("resulting equity would be negative")
    ts_ms = int(time.time() * 1000)
    conn.execute(
        """
        INSERT INTO paper.account_ledger (
            entry_id, account_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        ) VALUES (
            gen_random_uuid(), %s, %s, %s, %s, 'admin_adjustment', %s, '{}'::jsonb
        )
        """,
        (str(account_id), ts_ms, str(delta_usdt), str(nxt), note),
    )
    conn.execute(
        "UPDATE paper.accounts SET equity = %s WHERE account_id = %s",
        (str(nxt), str(account_id)),
    )
    return {"account_id": str(account_id), "equity_after": str(nxt), "ts_ms": ts_ms}


def paper_reset_demo_account(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    new_initial_equity: Decimal,
    purge_trade_evaluations: bool,
    note: str | None,
) -> dict[str, Any]:
    ts_ms = int(time.time() * 1000)
    acc_row = conn.execute(
        "SELECT equity FROM paper.accounts WHERE account_id = %s FOR UPDATE",
        (str(account_id),),
    ).fetchone()
    if not acc_row:
        raise ValueError("account not found")
    equity_before = Decimal(str(dict(acc_row)["equity"]))
    delta = new_initial_equity - equity_before
    pos_rows = conn.execute(
        "SELECT position_id FROM paper.positions WHERE account_id = %s",
        (str(account_id),),
    ).fetchall()
    pids = [str(dict(r)["position_id"]) for r in pos_rows]
    if pids:
        if purge_trade_evaluations:
            conn.execute(
                """
                DELETE FROM learn.trade_evaluations
                WHERE paper_trade_id = ANY(%s::uuid[])
                """,
                (pids,),
            )
        conn.execute(
            """
            UPDATE learn.e2e_decision_records
            SET paper_trade_id = NULL
            WHERE paper_trade_id = ANY(%s::uuid[])
            """,
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.position_events WHERE position_id = ANY(%s::uuid[])",
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.funding_ledger WHERE position_id = ANY(%s::uuid[])",
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.fee_ledger WHERE position_id = ANY(%s::uuid[])",
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.fills WHERE position_id = ANY(%s::uuid[])",
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.orders WHERE position_id = ANY(%s::uuid[])",
            (pids,),
        )
        conn.execute(
            "DELETE FROM paper.positions WHERE account_id = %s",
            (str(account_id),),
        )
    conn.execute(
        """
        UPDATE paper.accounts
        SET initial_equity = %s, equity = %s
        WHERE account_id = %s
        """,
        (str(new_initial_equity), str(new_initial_equity), str(account_id)),
    )
    reset_meta = json.dumps(
        {
            "purged_positions": len(pids),
            "purge_trade_evaluations": purge_trade_evaluations,
        },
        separators=(",", ":"),
    )
    conn.execute(
        """
        INSERT INTO paper.account_ledger (
            entry_id, account_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        ) VALUES (
            gen_random_uuid(), %s, %s, %s, %s, 'admin_reset',
            %s,
            %s::jsonb
        )
        """,
        (
            str(account_id),
            ts_ms,
            str(delta),
            str(new_initial_equity),
            note,
            reset_meta,
        ),
    )
    return {
        "account_id": str(account_id),
        "positions_deleted": len(pids),
        "new_initial_equity": str(new_initial_equity),
        "equity_before": str(equity_before),
        "ts_ms": ts_ms,
    }
