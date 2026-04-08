from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass
class AlertRecord:
    alert_key: str
    severity: str
    title: str
    message: str
    details: dict[str, Any]
    state: str
    created_ts: Any
    updated_ts: Any


def upsert_alert(
    dsn: str,
    *,
    alert_key: str,
    severity: str,
    title: str,
    message: str,
    details: dict[str, Any],
) -> str:
    """Insert oder Update; bei resolved -> wieder open bei erneutem Fehler."""
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ops.alerts
                    (alert_key, severity, title, message, details, state, updated_ts)
                VALUES (%s, %s, %s, %s, %s::jsonb, 'open', now())
                ON CONFLICT (alert_key) DO UPDATE SET
                    severity = EXCLUDED.severity,
                    title = EXCLUDED.title,
                    message = EXCLUDED.message,
                    details = EXCLUDED.details,
                    updated_ts = now(),
                    state = CASE
                        WHEN ops.alerts.state = 'resolved' THEN 'open'
                        ELSE ops.alerts.state
                    END
                RETURNING alert_id::text
                """,
                (alert_key, severity, title, message, json.dumps(details)),
            )
            row = cur.fetchone()
            return str(row[0]) if row else ""


def list_open_alerts(dsn: str, *, limit: int = 50) -> list[AlertRecord]:
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT alert_key, severity, title, message, details, state, created_ts, updated_ts
                FROM ops.alerts
                WHERE state = 'open'
                ORDER BY updated_ts DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    out: list[AlertRecord] = []
    for row in rows:
        out.append(
            AlertRecord(
                alert_key=row[0],
                severity=row[1],
                title=row[2],
                message=row[3],
                details=row[4] if isinstance(row[4], dict) else {},
                state=row[5],
                created_ts=row[6],
                updated_ts=row[7],
            )
        )
    return out


def count_open_alerts(dsn: str) -> int:
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)::int
                FROM ops.alerts
                WHERE state = 'open'
                """
            )
            row = cur.fetchone()
    return int(row[0]) if row else 0


def ack_alert(dsn: str, alert_key: str) -> bool:
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ops.alerts SET state = 'acked', updated_ts = now()
                WHERE alert_key = %s
                """,
                (alert_key,),
            )
            return cur.rowcount > 0
