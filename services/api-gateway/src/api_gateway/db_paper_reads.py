from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg


def fetch_paper_account_ledger_recent(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    limit: int,
) -> list[dict[str, Any]]:
    lim = max(1, min(200, int(limit)))
    rows = conn.execute(
        """
        SELECT entry_id, ts_ms, amount_usdt, balance_after, reason, note, meta
        FROM paper.account_ledger
        WHERE account_id = %s
        ORDER BY ts_ms DESC
        LIMIT %s
        """,
        (str(account_id), lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        meta = d.get("meta")
        if hasattr(meta, "keys"):
            meta_d: dict[str, Any] = dict(meta)
        else:
            meta_d = {}
        out.append(
            {
                "entry_id": str(d["entry_id"]),
                "ts_ms": int(d["ts_ms"]),
                "amount_usdt": str(d["amount_usdt"]),
                "balance_after": str(d["balance_after"]),
                "reason": d["reason"],
                "note": d.get("note"),
                "meta": meta_d,
            }
        )
    return out


def fetch_paper_journal_recent(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    limit: int,
    symbol: str | None,
) -> list[dict[str, Any]]:
    lim = max(1, min(300, int(limit)))
    sym = symbol.upper().strip() if symbol else None
    rows = conn.execute(
        """
        SELECT * FROM (
            SELECT
                'account_ledger' AS source,
                entry_id::text AS ref_id,
                ts_ms,
                jsonb_build_object(
                    'reason', reason,
                    'amount_usdt', amount_usdt::text,
                    'balance_after', balance_after::text,
                    'note', note
                ) AS detail,
                NULL::text AS symbol
            FROM paper.account_ledger
            WHERE account_id = %s
            UNION ALL
            SELECT
                'position_event' AS source,
                pe.event_id::text AS ref_id,
                pe.ts_ms,
                jsonb_build_object('type', pe.type, 'details', pe.details) AS detail,
                p.symbol
            FROM paper.position_events pe
            JOIN paper.positions p ON p.position_id = pe.position_id
            WHERE p.account_id = %s
              AND (%s IS NULL OR UPPER(TRIM(p.symbol)) = %s)
        ) sub
        ORDER BY ts_ms DESC
        LIMIT %s
        """,
        (str(account_id), str(account_id), sym, sym, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        detail = d.get("detail")
        if hasattr(detail, "keys"):
            detail_obj: Any = dict(detail)
        else:
            detail_obj = json.loads(str(detail)) if detail else {}
        out.append(
            {
                "source": d["source"],
                "ref_id": d["ref_id"],
                "ts_ms": int(d["ts_ms"]),
                "symbol": d.get("symbol"),
                "detail": detail_obj,
            }
        )
    return out
