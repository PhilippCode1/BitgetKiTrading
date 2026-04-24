from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import psycopg


def insert_position_event(
    conn: psycopg.Connection[Any],
    *,
    position_id: UUID,
    ts_ms: int,
    event_type: str,
    details: dict[str, Any],
) -> UUID:
    eid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.position_events (event_id, position_id, ts_ms, type, details)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (
            str(eid),
            str(position_id),
            ts_ms,
            event_type,
            json.dumps(details, separators=(",", ":"), ensure_ascii=False),
        ),
    )
    return eid


def list_account_equity_points(
    conn: psycopg.Connection[Any],
    *,
    account_id: UUID,
    tenant_id: str,
    since_ts_ms: int | None = None,
    limit: int = 5000,
) -> list[str]:
    tid = str(tenant_id).strip() or "default"
    params: list[Any] = [str(account_id), tid]
    since_clause = ""
    if since_ts_ms is not None:
        since_clause = "AND pe.ts_ms >= %s"
        params.append(int(since_ts_ms))
    params.append(int(limit))
    rows = conn.execute(
        f"""
        SELECT COALESCE(
            pe.details->>'account_total_equity_after',
            pe.details->>'account_equity_after'
        ) AS equity
        FROM paper.position_events pe
        JOIN paper.positions p ON p.position_id = pe.position_id
        WHERE p.account_id = %s
          AND p.tenant_id = %s
          AND COALESCE(
            pe.details->>'account_total_equity_after',
            pe.details->>'account_equity_after'
          ) IS NOT NULL
          {since_clause}
        ORDER BY pe.ts_ms DESC
        LIMIT %s
        """,
        tuple(params),
    ).fetchall()
    out: list[str] = []
    for row in rows:
        value = row["equity"]
        if value not in (None, ""):
            out.append(str(value))
    return out
