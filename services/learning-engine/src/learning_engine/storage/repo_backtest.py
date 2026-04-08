from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg


def insert_backtest_run(
    conn: psycopg.Connection[Any],
    *,
    run_id: UUID,
    symbol: str,
    timeframes_json: list[str],
    mode: str,
    from_ts_ms: int,
    to_ts_ms: int,
    cv_method: str,
    params_json: dict[str, Any],
    metrics_json: dict[str, Any],
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO learn.backtest_runs (
            run_id, symbol, timeframes_json, mode, from_ts_ms, to_ts_ms,
            cv_method, params_json, metrics_json, status
        ) VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
        ON CONFLICT (run_id) DO UPDATE SET
            symbol = EXCLUDED.symbol,
            timeframes_json = EXCLUDED.timeframes_json,
            mode = EXCLUDED.mode,
            from_ts_ms = EXCLUDED.from_ts_ms,
            to_ts_ms = EXCLUDED.to_ts_ms,
            cv_method = EXCLUDED.cv_method,
            params_json = EXCLUDED.params_json,
            metrics_json = EXCLUDED.metrics_json,
            status = EXCLUDED.status
        """,
        (
            str(run_id),
            symbol,
            json.dumps(timeframes_json),
            mode,
            from_ts_ms,
            to_ts_ms,
            cv_method,
            json.dumps(params_json, default=str),
            json.dumps(metrics_json, default=str),
            status,
        ),
    )


def delete_backtest_folds_for_run(conn: psycopg.Connection[Any], *, run_id: UUID) -> None:
    conn.execute("DELETE FROM learn.backtest_folds WHERE run_id = %s", (str(run_id),))


def update_backtest_run(
    conn: psycopg.Connection[Any],
    *,
    run_id: UUID,
    metrics_json: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    parts: list[str] = []
    args: list[Any] = []
    if metrics_json is not None:
        parts.append("metrics_json = %s::jsonb")
        args.append(json.dumps(metrics_json, default=str))
    if status is not None:
        parts.append("status = %s")
        args.append(status)
    if not parts:
        return
    args.append(str(run_id))
    conn.execute(
        f"UPDATE learn.backtest_runs SET {', '.join(parts)} WHERE run_id = %s",
        tuple(args),
    )


def insert_backtest_fold(
    conn: psycopg.Connection[Any],
    *,
    run_id: UUID,
    fold_index: int,
    train_range_json: dict[str, Any],
    test_range_json: dict[str, Any],
    metrics_json: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO learn.backtest_folds
            (run_id, fold_index, train_range_json, test_range_json, metrics_json)
        VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        """,
        (
            str(run_id),
            fold_index,
            json.dumps(train_range_json, default=str),
            json.dumps(test_range_json, default=str),
            json.dumps(metrics_json, default=str),
        ),
    )


def list_backtest_runs(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT run_id, symbol, timeframes_json, mode, from_ts_ms, to_ts_ms,
               cv_method, params_json, metrics_json, status, created_ts
        FROM learn.backtest_runs
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_backtest_run(conn: psycopg.Connection[Any], run_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT run_id, symbol, timeframes_json, mode, from_ts_ms, to_ts_ms,
               cv_method, params_json, metrics_json, status, created_ts
        FROM learn.backtest_runs WHERE run_id = %s
        """,
        (str(run_id),),
    ).fetchone()
    return dict(row) if row else None


def list_folds_for_run(conn: psycopg.Connection[Any], run_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT fold_id, run_id, fold_index, train_range_json, test_range_json, metrics_json
        FROM learn.backtest_folds
        WHERE run_id = %s
        ORDER BY fold_index ASC
        """,
        (str(run_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_trade_evaluations_window(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    from_ts_ms: int,
    to_ts_ms: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM learn.trade_evaluations
        WHERE symbol = %s
          AND decision_ts_ms >= %s
          AND decision_ts_ms <= %s
        ORDER BY decision_ts_ms ASC, closed_ts_ms ASC, evaluation_id ASC
        """,
        (symbol.upper(), from_ts_ms, to_ts_ms),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_trade_evaluations_benchmark_sample(
    conn: psycopg.Connection[Any],
    *,
    symbol: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Neueste geschlossene Evaluations fuer Research-Benchmarks (DESC)."""
    lim = max(1, min(int(limit), 50_000))
    if symbol:
        rows = conn.execute(
            """
            SELECT *
            FROM learn.trade_evaluations
            WHERE symbol = %s AND closed_ts_ms IS NOT NULL
            ORDER BY decision_ts_ms DESC, closed_ts_ms DESC
            LIMIT %s
            """,
            (symbol.upper(), lim),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT *
            FROM learn.trade_evaluations
            WHERE closed_ts_ms IS NOT NULL
            ORDER BY decision_ts_ms DESC, closed_ts_ms DESC
            LIMIT %s
            """,
            (lim,),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_replay_session(
    conn: psycopg.Connection[Any],
    *,
    session_id: UUID,
    from_ts_ms: int,
    to_ts_ms: int,
    speed_factor: float,
    status: str,
    manifest_json: dict[str, Any] | None = None,
) -> None:
    manifest = manifest_json if manifest_json is not None else {}
    conn.execute(
        """
        INSERT INTO learn.replay_sessions (
            session_id, from_ts_ms, to_ts_ms, speed_factor, status, manifest_json
        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (session_id) DO UPDATE SET
            from_ts_ms = EXCLUDED.from_ts_ms,
            to_ts_ms = EXCLUDED.to_ts_ms,
            speed_factor = EXCLUDED.speed_factor,
            status = EXCLUDED.status,
            manifest_json = EXCLUDED.manifest_json
        """,
        (
            str(session_id),
            from_ts_ms,
            to_ts_ms,
            str(speed_factor),
            status,
            json.dumps(manifest, default=str),
        ),
    )


def update_replay_session(
    conn: psycopg.Connection[Any], *, session_id: UUID, status: str
) -> None:
    conn.execute(
        "UPDATE learn.replay_sessions SET status = %s WHERE session_id = %s",
        (status, str(session_id)),
    )
