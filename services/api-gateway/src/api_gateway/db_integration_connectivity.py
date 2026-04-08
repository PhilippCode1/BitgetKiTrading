"""Persistente Integrations-Health (Migration 602); keine Secrets."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Json


def fetch_integration_connectivity_map(
    conn: psycopg.Connection[Any],
) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT integration_key, last_status, last_error_public,
               last_success_ts, last_failure_ts, probe_detail_json, updated_ts
        FROM app.integration_connectivity_state
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        key = str(d.pop("integration_key"))
        out[key] = d
    return out


def upsert_integration_connectivity_rows(
    conn: psycopg.Connection[Any],
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        conn.execute(
            """
            INSERT INTO app.integration_connectivity_state (
                integration_key, last_status, last_error_public,
                last_success_ts, last_failure_ts, probe_detail_json, updated_ts
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (integration_key) DO UPDATE SET
                last_status = EXCLUDED.last_status,
                last_error_public = EXCLUDED.last_error_public,
                last_success_ts = EXCLUDED.last_success_ts,
                last_failure_ts = EXCLUDED.last_failure_ts,
                probe_detail_json = EXCLUDED.probe_detail_json,
                updated_ts = EXCLUDED.updated_ts
            """,
            (
                row["integration_key"],
                row["last_status"][:64],
                row["last_error_public"],
                row["last_success_ts"],
                row["last_failure_ts"],
                Json(row["probe_detail_json"]),
                row["updated_ts"],
            ),
        )
