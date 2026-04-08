from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import psycopg
from psycopg import errors as pg_errors
_TAKE_TRADE = "take_trade_prob"


def fetch_online_drift_state(conn: psycopg.Connection[Any], *, scope: str = "global") -> dict[str, Any] | None:
    try:
        row = conn.execute(
            """
            SELECT scope, effective_action, computed_at, lookback_minutes, breakdown_json, drift_event_ids
            FROM learn.online_drift_state
            WHERE scope = %s
            """,
            (scope,),
        ).fetchone()
    except pg_errors.UndefinedTable:
        return None
    return dict(row) if row else None


def fetch_drift_events_recent(conn: psycopg.Connection[Any], *, limit: int) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT drift_id, metric_name, severity, details_json, detected_ts
            FROM learn.drift_events
            ORDER BY detected_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        ts = d.get("detected_ts")
        out.append(
            {
                "drift_id": str(d["drift_id"]),
                "metric_name": d["metric_name"],
                "severity": d["severity"],
                "details_json": d.get("details_json") or {},
                "detected_ts": ts.isoformat() if ts is not None else None,
            }
        )
    return out


def upsert_online_drift_state(
    conn: psycopg.Connection[Any],
    *,
    scope: str,
    effective_action: str,
    lookback_minutes: int,
    breakdown_json: dict[str, Any],
    drift_event_ids: list[UUID],
) -> None:
    conn.execute(
        """
        INSERT INTO learn.online_drift_state (
            scope, effective_action, computed_at, lookback_minutes, breakdown_json, drift_event_ids
        )
        VALUES (%s, %s, now(), %s, %s::jsonb, %s::uuid[])
        ON CONFLICT (scope) DO UPDATE SET
            effective_action = EXCLUDED.effective_action,
            computed_at = EXCLUDED.computed_at,
            lookback_minutes = EXCLUDED.lookback_minutes,
            breakdown_json = EXCLUDED.breakdown_json,
            drift_event_ids = EXCLUDED.drift_event_ids
        """,
        (
            scope,
            effective_action,
            lookback_minutes,
            json.dumps(breakdown_json, default=str),
            drift_event_ids,
        ),
    )


def fetch_recent_signals_for_online_drift(
    conn: psycopg.Connection[Any],
    *,
    lookback_minutes: int,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT signal_id, market_regime, take_trade_prob, model_ood_score_0_1, model_ood_alert,
               rejection_reasons_json, source_snapshot_json, created_at
        FROM app.signals_v1
        WHERE created_at >= now() - (%s::bigint * interval '1 minute')
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (lookback_minutes, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_take_trade_champion_reference(conn: psycopg.Connection[Any]) -> dict[str, Any] | None:
    try:
        row = conn.execute(
            """
            SELECT r.metadata_json, r.metrics_json
            FROM app.model_registry_v2 g
            INNER JOIN app.model_runs r
                ON r.run_id = g.run_id AND r.model_name = g.model_name
            WHERE g.model_name = %s AND g.role = 'champion'
              AND g.scope_type = 'global' AND g.scope_key = ''
            LIMIT 1
            """,
            (_TAKE_TRADE,),
        ).fetchone()
        if row:
            return dict(row)
    except pg_errors.UndefinedTable:
        pass
    row = conn.execute(
        """
        SELECT metadata_json, metrics_json
        FROM app.model_runs
        WHERE model_name = %s AND promoted_bool = true
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (_TAKE_TRADE,),
    ).fetchone()
    return dict(row) if row else None


def audit_online_drift_transition(
    conn: psycopg.Connection[Any],
    *,
    previous_action: str,
    new_action: str,
    payload: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.audit_log (entity_schema, entity_table, entity_id, action, payload)
        VALUES ('learn', 'online_drift_state', 'global', %s, %s::jsonb)
        """,
        (
            f"online_drift_{previous_action}_to_{new_action}",
            json.dumps(
                {
                    "previous_effective_action": previous_action,
                    "new_effective_action": new_action,
                    **payload,
                },
                default=str,
            ),
        ),
    )
