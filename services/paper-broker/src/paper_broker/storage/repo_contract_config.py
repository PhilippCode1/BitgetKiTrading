"""Optional: Queries auf contract_config_snapshots (Historie)."""

from __future__ import annotations

from typing import Any

import psycopg


def latest_snapshot_row(
    conn: psycopg.Connection[Any], symbol: str, product_type: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM paper.contract_config_snapshots
        WHERE symbol = %s AND product_type = %s
        ORDER BY captured_ts_ms DESC
        LIMIT 1
        """,
        (symbol, product_type),
    ).fetchone()
    return dict(row) if row else None
