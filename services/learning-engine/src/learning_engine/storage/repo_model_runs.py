from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg

_ALLOWED_TRAINING_TARGET_FIELDS = {
    "take_trade_label",
    "expected_return_bps",
    "expected_mae_bps",
    "expected_mfe_bps",
}


def insert_model_run(
    conn: psycopg.Connection[Any],
    *,
    run_id: UUID,
    model_name: str,
    version: str,
    dataset_hash: str,
    metrics_json: dict[str, Any],
    promoted_bool: bool,
    artifact_path: str | None,
    target_name: str | None,
    output_field: str | None,
    calibration_method: str | None,
    metadata_json: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.model_runs (
            run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
            artifact_path, target_name, output_field, calibration_method, metadata_json
        ) VALUES (
            %s, %s, %s, %s, %s::jsonb, %s,
            %s, %s, %s, %s, %s::jsonb
        )
        """,
        (
            str(run_id),
            model_name,
            version,
            dataset_hash,
            json.dumps(metrics_json, default=str),
            promoted_bool,
            artifact_path,
            target_name,
            output_field,
            calibration_method,
            json.dumps(metadata_json, default=str),
        ),
    )


def clear_promoted_model(conn: psycopg.Connection[Any], *, model_name: str) -> None:
    conn.execute(
        "UPDATE app.model_runs SET promoted_bool = false WHERE model_name = %s",
        (model_name,),
    )


def get_latest_model_run(
    conn: psycopg.Connection[Any],
    *,
    model_name: str,
    promoted_only: bool = True,
) -> dict[str, Any] | None:
    sql = """
    SELECT run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
           artifact_path, target_name, output_field, calibration_method, metadata_json, created_ts
    FROM app.model_runs
    WHERE model_name = %s
    """
    params: list[Any] = [model_name]
    if promoted_only:
        sql += " AND promoted_bool = true"
    sql += " ORDER BY created_ts DESC LIMIT 1"
    row = conn.execute(sql, tuple(params)).fetchone()
    return dict(row) if row else None


def list_model_runs(
    conn: psycopg.Connection[Any],
    *,
    model_name: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    sql = """
    SELECT run_id, model_name, version, dataset_hash, metrics_json, promoted_bool,
           artifact_path, target_name, output_field, calibration_method, metadata_json, created_ts
    FROM app.model_runs
    """
    params: list[Any] = []
    if model_name:
        sql += " WHERE model_name = %s"
        params.append(model_name)
    sql += " ORDER BY created_ts DESC LIMIT %s"
    params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def fetch_take_trade_training_rows(
    conn: psycopg.Connection[Any],
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    return fetch_target_training_rows(conn, target_field="take_trade_label", symbol=symbol)


def fetch_regime_training_rows(
    conn: psycopg.Connection[Any],
    *,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
    SELECT *
    FROM learn.trade_evaluations
    WHERE market_regime IS NOT NULL
    """
    params: list[Any] = []
    if symbol:
        sql += " AND symbol = %s"
        params.append(symbol.upper())
    sql += " ORDER BY decision_ts_ms ASC, closed_ts_ms ASC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def fetch_target_training_rows(
    conn: psycopg.Connection[Any],
    *,
    target_field: str,
    symbol: str | None = None,
) -> list[dict[str, Any]]:
    if target_field not in _ALLOWED_TRAINING_TARGET_FIELDS:
        raise ValueError(f"unsupported target_field: {target_field!r}")
    sql = """
    SELECT *
    FROM learn.trade_evaluations
    WHERE %s IS NOT NULL
    """
    sql = sql.replace("%s", target_field, 1)
    params: list[Any] = []
    if symbol:
        sql += " AND symbol = %s"
        params.append(symbol.upper())
    sql += " ORDER BY decision_ts_ms ASC, closed_ts_ms ASC"
    rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(r) for r in rows]


def jsonable_row(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(row), default=str))
