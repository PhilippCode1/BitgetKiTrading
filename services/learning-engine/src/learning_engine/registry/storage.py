from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from shared_py.strategy_config_hash import compute_configuration_hash


def insert_strategy(
    conn: psycopg.Connection[Any],
    *,
    name: str,
    description: str,
    scope_json: dict[str, Any],
    initial_status: str,
) -> dict[str, Any]:
    scope_txt = json.dumps(scope_json)
    row = conn.execute(
        """
        INSERT INTO learn.strategies (name, description, scope_json)
        VALUES (%s, %s, %s::jsonb)
        RETURNING strategy_id, name, description, scope_json, created_ts, updated_ts
        """,
        (name, description, scope_txt),
    ).fetchone()
    assert row is not None
    sid = row["strategy_id"]
    conn.execute(
        """
        INSERT INTO learn.strategy_status (strategy_id, current_status)
        VALUES (%s, %s)
        """,
        (sid, initial_status),
    )
    conn.execute(
        """
        INSERT INTO learn.strategy_status_history
            (strategy_id, old_status, new_status, reason, changed_by)
        VALUES (%s, NULL, %s, %s, %s)
        """,
        (sid, initial_status, "initial create", "system"),
    )
    return dict(row)


def insert_version(
    conn: psycopg.Connection[Any],
    *,
    strategy_id: UUID,
    version: str,
    definition_json: dict[str, Any],
    parameters_json: dict[str, Any],
    risk_profile_json: dict[str, Any],
) -> dict[str, Any]:
    h = compute_configuration_hash(definition_json, parameters_json, risk_profile_json)
    row = conn.execute(
        """
        INSERT INTO learn.strategy_versions
            (strategy_id, version, definition_json, parameters_json,
             risk_profile_json, configuration_hash)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        RETURNING strategy_version_id, strategy_id, version, definition_json,
                  parameters_json, risk_profile_json, configuration_hash, created_ts
        """,
        (
            strategy_id,
            version,
            json.dumps(definition_json),
            json.dumps(parameters_json),
            json.dumps(risk_profile_json),
            h,
        ),
    ).fetchone()
    assert row is not None
    return dict(row)


def fetch_strategy_by_id(conn: psycopg.Connection[Any], strategy_id: UUID) -> dict[str, Any] | None:
    return conn.execute(
        """
        SELECT s.strategy_id, s.name, s.description, s.scope_json, s.created_ts, s.updated_ts,
               st.current_status
        FROM learn.strategies s
        LEFT JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
        WHERE s.strategy_id = %s
        """,
        (strategy_id,),
    ).fetchone()


def list_strategies(
    conn: psycopg.Connection[Any], *, status: str | None = None
) -> list[dict[str, Any]]:
    if status:
        rows = conn.execute(
            """
            SELECT s.strategy_id, s.name, s.description, s.scope_json, s.created_ts, s.updated_ts,
                   st.current_status
            FROM learn.strategies s
            JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
            WHERE st.current_status = %s
            ORDER BY s.name ASC
            """,
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT s.strategy_id, s.name, s.description, s.scope_json, s.created_ts, s.updated_ts,
                   st.current_status
            FROM learn.strategies s
            LEFT JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
            ORDER BY s.name ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_versions(conn: psycopg.Connection[Any], strategy_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT strategy_version_id, strategy_id, version, definition_json, parameters_json,
               risk_profile_json, configuration_hash, created_ts
        FROM learn.strategy_versions
        WHERE strategy_id = %s
        ORDER BY created_ts DESC
        """,
        (strategy_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_current_status(conn: psycopg.Connection[Any], strategy_id: UUID) -> str | None:
    row = conn.execute(
        "SELECT current_status FROM learn.strategy_status WHERE strategy_id = %s",
        (strategy_id,),
    ).fetchone()
    if row is None:
        return None
    return str(row["current_status"])


def update_status(
    conn: psycopg.Connection[Any],
    *,
    strategy_id: UUID,
    new_status: str,
    old_status: str | None,
    reason: str | None,
    changed_by: str,
    live_champion_version_id: UUID | None = None,
) -> None:
    if new_status == "live_champion":
        if live_champion_version_id is None:
            raise ValueError("live_champion erfordert live_champion_version_id")
        conn.execute(
            """
            UPDATE learn.strategy_status
            SET current_status = %s, updated_ts = now(),
                live_champion_version_id = %s
            WHERE strategy_id = %s
            """,
            (new_status, str(live_champion_version_id), str(strategy_id)),
        )
    else:
        conn.execute(
            """
            UPDATE learn.strategy_status
            SET current_status = %s, updated_ts = now(),
                live_champion_version_id = NULL
            WHERE strategy_id = %s
            """,
            (new_status, str(strategy_id)),
        )
    conn.execute(
        """
        INSERT INTO learn.strategy_status_history
            (strategy_id, old_status, new_status, reason, changed_by)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (strategy_id, old_status, new_status, reason, changed_by),
    )
    conn.execute(
        "UPDATE learn.strategies SET updated_ts = now() WHERE strategy_id = %s",
        (strategy_id,),
    )


def list_promoted_names(conn: psycopg.Connection[Any]) -> list[str]:
    rows = conn.execute(
        """
        SELECT s.name
        FROM learn.strategies s
        JOIN learn.strategy_status st ON st.strategy_id = s.strategy_id
        WHERE st.current_status IN ('promoted', 'live_champion')
        ORDER BY s.name ASC
        """
    ).fetchall()
    return [str(r["name"]) for r in rows]
