from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg


def fetch_model_run_by_id(conn: psycopg.Connection[Any], *, run_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
               artifact_path, target_name, output_field, calibration_method, metadata_json, created_ts
        FROM app.model_runs
        WHERE run_id = %s
        """,
        (str(run_id),),
    ).fetchone()
    return dict(row) if row else None


def upsert_registry_slot(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    role: str,
    run_id: UUID,
    calibration_status: str,
    notes: str | None = None,
    scope_type: str = "global",
    scope_key: str = "",
) -> dict[str, Any]:
    row = conn.execute(
        """
        INSERT INTO app.model_registry_v2 (
            model_name, role, run_id, calibration_status, notes, activated_ts, scope_type, scope_key
        )
        VALUES (%s, %s, %s, %s, %s, now(), %s, %s)
        ON CONFLICT (model_name, role, scope_type, scope_key) DO UPDATE SET
            run_id = EXCLUDED.run_id,
            calibration_status = EXCLUDED.calibration_status,
            notes = EXCLUDED.notes,
            activated_ts = now(),
            updated_ts = now()
        RETURNING registry_id, model_name, role, run_id, calibration_status, activated_ts, notes,
                  created_ts, updated_ts, scope_type, scope_key
        """,
        (model_name, role, str(run_id), calibration_status, notes, scope_type, scope_key),
    ).fetchone()
    assert row is not None
    return dict(row)


def list_registry_with_runs(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT g.registry_id, g.model_name, g.role, g.run_id, g.calibration_status, g.activated_ts,
               g.notes, g.created_ts, g.updated_ts, g.scope_type, g.scope_key,
               r.version, r.dataset_hash, r.metrics_json, r.promoted_bool,
               r.calibration_method, r.artifact_path, r.metadata_json, r.created_ts AS run_created_ts
        FROM app.model_registry_v2 g
        JOIN app.model_runs r ON r.run_id = g.run_id AND r.model_name = g.model_name
        ORDER BY g.model_name ASC, g.scope_type ASC, g.scope_key ASC, g.role ASC
        """
    ).fetchall()
    return [dict(x) for x in rows]


def delete_slot(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    role: str,
    scope_type: str = "global",
    scope_key: str = "",
) -> bool:
    cur = conn.execute(
        """
        DELETE FROM app.model_registry_v2
        WHERE model_name = %s AND role = %s AND scope_type = %s AND scope_key = %s
        """,
        (model_name, role, scope_type, scope_key),
    )
    return cur.rowcount > 0


def fetch_champion_run_joined(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    scope_type: str,
    scope_key: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.run_id, r.model_name, r.version, r.dataset_hash, r.metrics_json, r.promoted_bool,
               r.artifact_path, r.target_name, r.output_field, r.calibration_method, r.metadata_json,
               r.created_ts,
               g.role AS registry_role,
               g.calibration_status AS registry_calibration_status,
               g.activated_ts AS registry_activated_ts,
               g.scope_type AS registry_scope_type,
               g.scope_key AS registry_scope_key
        FROM app.model_runs r
        INNER JOIN app.model_registry_v2 g
            ON g.run_id = r.run_id AND g.model_name = r.model_name
        WHERE r.model_name = %s AND g.role = 'champion'
          AND g.scope_type = %s AND g.scope_key = %s
        LIMIT 1
        """,
        (model_name, scope_type, scope_key),
    ).fetchone()
    return dict(row) if row else None


def fetch_challenger_run_joined(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    scope_type: str,
    scope_key: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT r.run_id, r.model_name, r.version, r.dataset_hash, r.metrics_json, r.promoted_bool,
               r.artifact_path, r.target_name, r.output_field, r.calibration_method, r.metadata_json,
               r.created_ts,
               g.role AS registry_role,
               g.calibration_status AS registry_calibration_status,
               g.activated_ts AS registry_activated_ts,
               g.scope_type AS registry_scope_type,
               g.scope_key AS registry_scope_key,
               g.notes AS registry_notes
        FROM app.model_runs r
        INNER JOIN app.model_registry_v2 g
            ON g.run_id = r.run_id AND g.model_name = r.model_name
        WHERE r.model_name = %s AND g.role = 'challenger'
          AND g.scope_type = %s AND g.scope_key = %s
        LIMIT 1
        """,
        (model_name, scope_type, scope_key),
    ).fetchone()
    return dict(row) if row else None
