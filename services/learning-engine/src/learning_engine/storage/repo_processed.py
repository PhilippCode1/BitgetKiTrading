from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg


def already_processed(conn: psycopg.Connection[Any], stream: str, message_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM learn.processed_events WHERE stream = %s AND message_id = %s",
        (stream, message_id),
    ).fetchone()
    return row is not None


def mark_processed(conn: psycopg.Connection[Any], stream: str, message_id: str) -> None:
    conn.execute(
        """
        INSERT INTO learn.processed_events (stream, message_id, processed_ts)
        VALUES (%s, %s, %s)
        ON CONFLICT (stream, message_id) DO NOTHING
        """,
        (stream, message_id, datetime.now(UTC)),
    )
