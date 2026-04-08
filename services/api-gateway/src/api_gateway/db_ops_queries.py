from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg import errors as pg_errors


def _j(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def fetch_monitor_open_alerts(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT alert_key, severity, title, message, details, state, created_ts, updated_ts
            FROM ops.alerts
            WHERE state = 'open'
            ORDER BY updated_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "alert_key": str(data["alert_key"]),
                "severity": str(data["severity"]),
                "title": str(data["title"]),
                "message": str(data["message"]),
                "details": _j(data.get("details")) or {},
                "state": str(data["state"]),
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
                "updated_ts": data["updated_ts"].isoformat() if data.get("updated_ts") else None,
            }
        )
    return out


def fetch_alert_outbox_recent(
    conn: psycopg.Connection[Any], *, limit: int
) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT alert_id, created_ts, alert_type, severity, symbol, timeframe,
                   dedupe_key, chat_id, state, attempt_count, last_error,
                   telegram_message_id, sent_ts, payload
            FROM alert.alert_outbox
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    except pg_errors.UndefinedTable:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        out.append(
            {
                "alert_id": str(data["alert_id"]),
                "created_ts": data["created_ts"].isoformat() if data.get("created_ts") else None,
                "alert_type": str(data["alert_type"]),
                "severity": str(data["severity"]),
                "symbol": data.get("symbol"),
                "timeframe": data.get("timeframe"),
                "dedupe_key": data.get("dedupe_key"),
                "chat_id": int(data["chat_id"]) if data.get("chat_id") is not None else None,
                "state": str(data["state"]),
                "attempt_count": int(data["attempt_count"]) if data.get("attempt_count") is not None else None,
                "last_error": data.get("last_error"),
                "telegram_message_id": data.get("telegram_message_id"),
                "sent_ts": data["sent_ts"].isoformat() if data.get("sent_ts") else None,
                "payload": _j(data.get("payload")) or {},
            }
        )
    return out


def fetch_ops_summary(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    alert_count_row = conn.execute(
        """
        SELECT count(*)::int AS total
        FROM ops.alerts
        WHERE state = 'open'
        """
    ).fetchone()
    outbox_rows = conn.execute(
        """
        SELECT state, count(*)::int AS total
        FROM alert.alert_outbox
        GROUP BY state
        """
    ).fetchall()
    latest_reconcile = conn.execute(
        """
        SELECT status, created_ts, details_json
        FROM live.reconcile_snapshots
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    kill_switch_count_row = conn.execute(
        """
        SELECT count(*)::int AS total
        FROM (
            SELECT DISTINCT ON (scope, scope_key) *
            FROM live.kill_switch_events
            WHERE event_type IN ('arm', 'release')
            ORDER BY scope, scope_key, created_ts DESC
        ) latest
        WHERE is_active = true
        """
    ).fetchone()
    last_fill_row = conn.execute(
        """
        SELECT created_ts
        FROM live.fills
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    critical_audit_row = conn.execute(
        """
        SELECT count(*)::int AS total
        FROM live.audit_trails
        WHERE severity = 'critical'
          AND created_ts >= now() - interval '24 hours'
        """
    ).fetchone()
    order_rows = conn.execute(
        """
        SELECT status, count(*)::int AS total
        FROM live.orders
        GROUP BY status
        """
    ).fetchall()
    latch_row = conn.execute(
        """
        SELECT action
        FROM live.audit_trails
        WHERE category = 'safety_latch'
        ORDER BY created_ts DESC
        LIMIT 1
        """
    ).fetchone()
    safety_latch_active = (
        str(dict(latch_row).get("action") or "") == "arm" if latch_row is not None else False
    )

    outbox_counts = {str(row["state"]): int(row["total"]) for row in outbox_rows}
    latest_reconcile_data = dict(latest_reconcile) if latest_reconcile is not None else {}
    details = _j(latest_reconcile_data.get("details_json")) or {}
    drift = details.get("drift") if isinstance(details, dict) else {}
    latest_reconcile_ts = latest_reconcile_data.get("created_ts")
    latest_reconcile_age_ms = _age_ms(latest_reconcile_ts)
    last_fill_ts = last_fill_row["created_ts"] if last_fill_row is not None else None

    return {
        "monitor": {
            "open_alert_count": int(alert_count_row["total"]) if alert_count_row is not None else 0,
        },
        "alert_engine": {
            "outbox_pending": int(outbox_counts.get("pending", 0)),
            "outbox_failed": int(outbox_counts.get("failed", 0)),
            "outbox_sending": int(outbox_counts.get("sending", 0)),
        },
        "live_broker": {
            "latest_reconcile_status": latest_reconcile_data.get("status"),
            "latest_reconcile_created_ts": latest_reconcile_ts.isoformat()
            if hasattr(latest_reconcile_ts, "isoformat")
            else None,
            "latest_reconcile_age_ms": latest_reconcile_age_ms,
            "latest_reconcile_drift_total": int(
                drift.get("total_count") or 0
            )
            if isinstance(drift, dict)
            else 0,
            "active_kill_switch_count": int(kill_switch_count_row["total"])
            if kill_switch_count_row is not None
            else 0,
            "last_fill_created_ts": last_fill_ts.isoformat()
            if hasattr(last_fill_ts, "isoformat")
            else None,
            "last_fill_age_ms": _age_ms(last_fill_ts),
            "critical_audit_count_24h": int(critical_audit_row["total"])
            if critical_audit_row is not None
            else 0,
            "order_status_counts": {
                str(row["status"]): int(row["total"]) for row in order_rows
            },
            "safety_latch_active": safety_latch_active,
        },
    }


def _age_ms(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    elif isinstance(value, datetime):
        parsed = value
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() * 1000))
