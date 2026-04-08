"""Persistente Integrations-Health (letzte Fehler/Erfolge, ohne Secrets)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
import psycopg.errors
from psycopg.types.json import Json


def fetch_integration_connectivity_map(
    conn: psycopg.Connection[Any],
) -> dict[str, dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT integration_key, last_status, last_error_public,
                   last_success_ts, last_failure_ts, probe_detail_json, updated_ts
            FROM app.integration_connectivity_state
            """
        ).fetchall()
    except psycopg.errors.UndefinedTable:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        d = dict(row)
        key = str(d["integration_key"])
        out[key] = {
            "last_status": d.get("last_status"),
            "last_error_public": d.get("last_error_public"),
            "last_success_ts": d["last_success_ts"].isoformat()
            if d.get("last_success_ts")
            else None,
            "last_failure_ts": d["last_failure_ts"].isoformat()
            if d.get("last_failure_ts")
            else None,
            "probe_detail_json": d.get("probe_detail_json") or {},
            "updated_ts": d["updated_ts"].isoformat() if d.get("updated_ts") else None,
        }
    return out


def upsert_integration_connectivity_batch(
    conn: psycopg.Connection[Any],
    *,
    rows: list[dict[str, Any]],
) -> None:
    """
    rows: integration_key, health_status, error_public (optional), probe_detail (dict).

    Bei health_status=ok wird last_success_ts gesetzt und last_error_public geleert.
    Bei error/degraded/misconfigured: last_failure_ts + Fehlertext (gekuerzt).
    """
    now = datetime.now(timezone.utc)
    for r in rows:
        key = str(r["integration_key"])
        st = str(r.get("health_status") or "unknown")
        err_raw = r.get("error_public")
        err_s = (str(err_raw).strip()[:2000] if err_raw is not None else None) or None
        detail = r.get("probe_detail") if isinstance(r.get("probe_detail"), dict) else {}
        prev_row = conn.execute(
            """
            SELECT last_success_ts, last_failure_ts, last_error_public
            FROM app.integration_connectivity_state
            WHERE integration_key = %s
            """,
            (key,),
        ).fetchone()
        prev = dict(prev_row) if prev_row else {}
        last_success: datetime | None = prev.get("last_success_ts")
        last_failure: datetime | None = prev.get("last_failure_ts")
        last_error: str | None = prev.get("last_error_public")

        if st == "ok":
            last_success = now
            last_error = None
        elif st in ("error", "degraded", "misconfigured"):
            last_failure = now
            if err_s:
                last_error = err_s

        conn.execute(
            """
            INSERT INTO app.integration_connectivity_state (
                integration_key, last_status, last_error_public,
                last_success_ts, last_failure_ts, probe_detail_json, updated_ts
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (integration_key) DO UPDATE SET
                last_status = EXCLUDED.last_status,
                last_error_public = EXCLUDED.last_error_public,
                last_success_ts = EXCLUDED.last_success_ts,
                last_failure_ts = EXCLUDED.last_failure_ts,
                probe_detail_json = EXCLUDED.probe_detail_json,
                updated_ts = EXCLUDED.updated_ts
            """,
            (
                key,
                st,
                last_error,
                last_success,
                last_failure,
                Json(detail),
                now,
            ),
        )
