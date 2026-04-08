from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg


def window_to_ms(window: str) -> int:
    w = window.strip().lower()
    if w == "1d":
        return 86_400_000
    if w == "7d":
        return 7 * 86_400_000
    if w == "30d":
        return 30 * 86_400_000
    raise ValueError(f"unbekanntes window: {window!r}")


def fetch_evaluations_since_ms(
    conn: psycopg.Connection[Any], *, since_closed_ts_ms: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM learn.trade_evaluations
        WHERE closed_ts_ms >= %s
        ORDER BY closed_ts_ms ASC
        """,
        (since_closed_ts_ms,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_registry_strategies(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT strategy_id, name FROM learn.strategies ORDER BY name ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_strategy_metrics(
    conn: psycopg.Connection[Any],
    *,
    strategy_id: UUID,
    window: str,
    metrics_json: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO learn.strategy_metrics (strategy_id, time_window, metrics_json, updated_ts)
        VALUES (%s, %s, %s::jsonb, now())
        ON CONFLICT (strategy_id, time_window) DO UPDATE SET
            metrics_json = EXCLUDED.metrics_json,
            updated_ts = now()
        """,
        (str(strategy_id), window, json.dumps(metrics_json, default=str)),
    )


def clear_error_patterns_for_window(conn: psycopg.Connection[Any], *, window: str) -> None:
    conn.execute("DELETE FROM learn.error_patterns WHERE time_window = %s", (window,))


def insert_error_pattern(
    conn: psycopg.Connection[Any],
    *,
    window: str,
    pattern_key: str,
    count: int,
    examples_json: list[Any],
) -> None:
    conn.execute(
        """
        INSERT INTO learn.error_patterns (time_window, pattern_key, count, examples_json, updated_ts)
        VALUES (%s, %s, %s, %s::jsonb, now())
        """,
        (window, pattern_key, count, json.dumps(examples_json, default=str)),
    )


def insert_recommendation(
    conn: psycopg.Connection[Any],
    *,
    rec_type: str,
    payload_json: dict[str, Any],
    status: str = "new",
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO learn.recommendations (type, payload_json, status)
        VALUES (%s, %s::jsonb, %s)
        RETURNING rec_id
        """,
        (rec_type, json.dumps(payload_json, default=str), status),
    ).fetchone()
    assert row is not None
    return UUID(str(row["rec_id"]))


def insert_drift_event(
    conn: psycopg.Connection[Any],
    *,
    metric_name: str,
    severity: str,
    details_json: dict[str, Any],
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO learn.drift_events (metric_name, severity, details_json)
        VALUES (%s, %s, %s::jsonb)
        RETURNING drift_id
        """,
        (metric_name, severity, json.dumps(details_json, default=str)),
    ).fetchone()
    assert row is not None
    return UUID(str(row["drift_id"]))


def list_strategy_metrics(
    conn: psycopg.Connection[Any], *, window: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.strategy_id, s.name AS strategy_name, m.time_window AS window, m.metrics_json, m.updated_ts
        FROM learn.strategy_metrics m
        JOIN learn.strategies s ON s.strategy_id = m.strategy_id
        WHERE m.time_window = %s
        ORDER BY s.name ASC
        """,
        (window,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_error_patterns_top(
    conn: psycopg.Connection[Any], *, window: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT id, time_window AS window, pattern_key, count, examples_json, updated_ts
        FROM learn.error_patterns
        WHERE time_window = %s
        ORDER BY count DESC
        LIMIT %s
        """,
        (window, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_recent_recommendations(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT rec_id, type, payload_json, status, created_ts
        FROM learn.recommendations
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))
