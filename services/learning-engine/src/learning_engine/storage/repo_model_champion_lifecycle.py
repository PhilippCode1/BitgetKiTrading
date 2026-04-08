from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors


def fetch_registry_slot_run_id(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    role: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> UUID | None:
    try:
        row = conn.execute(
            """
            SELECT run_id FROM app.model_registry_v2
            WHERE model_name = %s AND role = %s AND scope_type = %s AND scope_key = %s
            LIMIT 1
            """,
            (model_name, role, scope_type, scope_key),
        ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    if not row:
        return None
    return UUID(str(row["run_id"]))


def close_open_champion_history(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    ended_reason: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> int:
    try:
        cur = conn.execute(
            """
            UPDATE app.model_champion_history
            SET ended_at = now(), ended_reason = %s
            WHERE model_name = %s AND ended_at IS NULL
              AND scope_type = %s AND scope_key = %s
            """,
            (ended_reason, model_name, scope_type, scope_key),
        )
        return int(cur.rowcount or 0)
    except pg_errors.UndefinedTable:
        return 0


def insert_champion_history_open(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    run_id: UUID,
    changed_by: str | None,
    promotion_gate_report: dict[str, Any],
    scope_type: str = "global",
    scope_key: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO app.model_champion_history (
            model_name, run_id, changed_by, promotion_gate_report, scope_type, scope_key
        )
        VALUES (%s, %s, %s, %s::jsonb, %s, %s)
        """,
        (
            model_name,
            str(run_id),
            changed_by,
            json.dumps(promotion_gate_report, default=str),
            scope_type,
            scope_key,
        ),
    )


def upsert_stable_checkpoint(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    run_id: UUID,
    marked_by: str,
    notes: str | None,
    scope_type: str = "global",
    scope_key: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO app.model_stable_champion_checkpoint (
            model_name, run_id, marked_by, notes, scope_type, scope_key
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (model_name, scope_type, scope_key) DO UPDATE SET
            run_id = EXCLUDED.run_id,
            marked_at = now(),
            marked_by = EXCLUDED.marked_by,
            notes = EXCLUDED.notes
        """,
        (model_name, str(run_id), marked_by, notes, scope_type, scope_key),
    )


def fetch_stable_checkpoint_run_id(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> UUID | None:
    try:
        row = conn.execute(
            """
            SELECT run_id FROM app.model_stable_champion_checkpoint
            WHERE model_name = %s AND scope_type = %s AND scope_key = %s
            LIMIT 1
            """,
            (model_name, scope_type, scope_key),
        ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    if not row:
        return None
    return UUID(str(row["run_id"]))
