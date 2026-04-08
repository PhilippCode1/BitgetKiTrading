from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg


def fetch_signal_v1(conn: psycopg.Connection[Any], signal_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM app.signals_v1 WHERE signal_id = %s",
        (str(signal_id),),
    ).fetchone()
    return dict(row) if row else None
