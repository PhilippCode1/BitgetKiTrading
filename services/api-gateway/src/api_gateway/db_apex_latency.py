"""Lese-Zugriff app.apex_latency_audit (Apex Core Latency)."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row


def fetch_apex_trace_by_signal_id(
    conn: psycopg.Connection[Any],
    *,
    signal_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT signal_id, execution_id, trace_id, apex_trace, created_at, updated_at "
        "FROM app.apex_latency_audit WHERE signal_id = %s LIMIT 1",
        (str(signal_id).strip()[:2000],),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    return d
