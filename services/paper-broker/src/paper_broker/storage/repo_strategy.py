from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import psycopg


def get_strategy_state(conn: psycopg.Connection[Any], key: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM paper.strategy_state WHERE key = %s",
        (key,),
    ).fetchone()
    return dict(row) if row else None


def upsert_strategy_state(
    conn: psycopg.Connection[Any],
    *,
    key: str,
    paused: bool,
    risk_off_until_ts_ms: int,
    last_signal_id: UUID | None,
    updated_ts_ms: int,
) -> None:
    conn.execute(
        """
        INSERT INTO paper.strategy_state (key, paused, risk_off_until_ts_ms, last_signal_id, updated_ts_ms)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (key) DO UPDATE SET
            paused = EXCLUDED.paused,
            risk_off_until_ts_ms = EXCLUDED.risk_off_until_ts_ms,
            last_signal_id = EXCLUDED.last_signal_id,
            updated_ts_ms = EXCLUDED.updated_ts_ms
        """,
        (
            key,
            paused,
            risk_off_until_ts_ms,
            str(last_signal_id) if last_signal_id else None,
            updated_ts_ms,
        ),
    )


def set_strategy_paused(conn: psycopg.Connection[Any], key: str, paused: bool, now_ms: int) -> None:
    row = get_strategy_state(conn, key)
    if row is None:
        upsert_strategy_state(
            conn,
            key=key,
            paused=paused,
            risk_off_until_ts_ms=0,
            last_signal_id=None,
            updated_ts_ms=now_ms,
        )
        return
    upsert_strategy_state(
        conn,
        key=key,
        paused=paused,
        risk_off_until_ts_ms=int(row["risk_off_until_ts_ms"] or 0),
        last_signal_id=UUID(str(row["last_signal_id"])) if row.get("last_signal_id") else None,
        updated_ts_ms=now_ms,
    )


def set_risk_off_until(
    conn: psycopg.Connection[Any], key: str, until_ts_ms: int, now_ms: int
) -> None:
    row = get_strategy_state(conn, key)
    paused = bool(row["paused"]) if row else False
    last_sid = UUID(str(row["last_signal_id"])) if row and row.get("last_signal_id") else None
    upsert_strategy_state(
        conn,
        key=key,
        paused=paused,
        risk_off_until_ts_ms=until_ts_ms,
        last_signal_id=last_sid,
        updated_ts_ms=now_ms,
    )


def insert_strategy_event(
    conn: psycopg.Connection[Any],
    *,
    ts_ms: int,
    event_type: str,
    details: dict[str, Any],
) -> UUID:
    eid = uuid4()
    conn.execute(
        """
        INSERT INTO paper.strategy_events (event_id, ts_ms, type, details)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (
            str(eid),
            ts_ms,
            event_type,
            json.dumps(details, separators=(",", ":"), ensure_ascii=False),
        ),
    )
    return eid


def list_recent_positions(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int = 20
) -> list[dict[str, Any]]:
    tid = str(tenant_id).strip() or "default"
    rows = conn.execute(
        """
        SELECT * FROM paper.positions
        WHERE tenant_id = %s
        ORDER BY opened_ts_ms DESC
        LIMIT %s
        """,
        (tid, limit),
    ).fetchall()
    return [dict(r) for r in rows]
