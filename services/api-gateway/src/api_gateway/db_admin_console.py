"""Aggregierte Lesepfade fuer Admin-Cockpit (Prompt 18)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg


def mask_tenant_id(tid: str) -> str:
    t = (tid or "").strip()
    if not t:
        return "—"
    if len(t) <= 8:
        return f"{t[:2]}…" if len(t) > 2 else t
    return f"{t[:4]}…{t[-4:]}"


def _iso_ts(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat().replace("+00:00", "Z")
    return str(v)


def fetch_lifecycle_status_counts(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT lifecycle_status, COUNT(*)::bigint AS cnt
        FROM app.tenant_customer_lifecycle
        GROUP BY lifecycle_status
        ORDER BY lifecycle_status
        """
    ).fetchall()
    return [
        {"lifecycle_status": str(dict(r)["lifecycle_status"]), "count": int(dict(r)["cnt"])}
        for r in rows
    ]


def fetch_lifecycle_recent(
    conn: psycopg.Connection[Any], *, limit: int = 18
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT tenant_id, lifecycle_status, email_verified,
               trial_started_at, trial_ends_at, updated_ts
        FROM app.tenant_customer_lifecycle
        ORDER BY updated_ts DESC NULLS LAST
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        tid = str(d.pop("tenant_id", "") or "")
        out.append(
            {
                "tenant_id_masked": mask_tenant_id(tid),
                "tenant_id": tid,
                "lifecycle_status": str(d.get("lifecycle_status") or ""),
                "email_verified": bool(d.get("email_verified")),
                "trial_started_at": _iso_ts(d.get("trial_started_at")),
                "trial_ends_at": _iso_ts(d.get("trial_ends_at")),
                "updated_ts": _iso_ts(d.get("updated_ts")),
            }
        )
    return out


def fetch_subscription_summary(conn: psycopg.Connection[Any]) -> dict[str, Any]:
    total_row = conn.execute(
        "SELECT COUNT(*)::bigint AS c FROM app.tenant_subscription"
    ).fetchone()
    total = int(dict(total_row or {})["c"] or 0)
    dunning_row = conn.execute(
        """
        SELECT COUNT(*)::bigint AS c
        FROM app.tenant_subscription
        WHERE dunning_stage IS NOT NULL
          AND length(trim(dunning_stage)) > 0
          AND lower(trim(dunning_stage)) NOT IN ('none', 'ok', 'healthy', 'clear', 'current')
        """
    ).fetchone()
    dunning = int(dict(dunning_row or {})["c"] or 0)
    return {"subscription_rows": total, "dunning_attention": dunning}


def fetch_contract_review_open_count(conn: psycopg.Connection[Any]) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)::bigint AS c
        FROM app.contract_review_queue
        WHERE queue_status IN ('pending_review', 'needs_customer_info')
        """
    ).fetchone()
    return int(dict(row or {})["c"] or 0)


def fetch_profit_fee_status_counts(
    conn: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT status, COUNT(*)::bigint AS cnt
        FROM app.profit_fee_statement
        GROUP BY status
        ORDER BY status
        """
    ).fetchall()
    return [
        {"status": str(dict(r)["status"]), "count": int(dict(r)["cnt"])} for r in rows
    ]


def fetch_integration_telegram_buckets(
    conn: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(trim(telegram_state), ''), '(empty)') AS bucket,
               COUNT(*)::bigint AS cnt
        FROM app.customer_integration_snapshot
        GROUP BY 1
        ORDER BY cnt DESC
        """
    ).fetchall()
    return [
        {"telegram_state": str(dict(r)["bucket"]), "count": int(dict(r)["cnt"])}
        for r in rows
    ]


def fetch_integration_broker_buckets(
    conn: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(trim(broker_state), ''), '(empty)') AS bucket,
               COUNT(*)::bigint AS cnt
        FROM app.customer_integration_snapshot
        GROUP BY 1
        ORDER BY cnt DESC
        """
    ).fetchall()
    return [
        {"broker_state": str(dict(r)["bucket"]), "count": int(dict(r)["cnt"])} for r in rows
    ]


def fetch_customer_telegram_binding_count(conn: psycopg.Connection[Any]) -> int:
    row = conn.execute(
        "SELECT COUNT(*)::bigint AS c FROM app.customer_telegram_binding"
    ).fetchone()
    return int(dict(row or {})["c"] or 0)


def fetch_customer_notify_outbox_recent(
    conn: psycopg.Connection[Any], *, limit: int = 50
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT alert_id, created_ts, severity, state, attempt_count, last_error,
               dedupe_key,
               payload->>'customer_category' AS customer_category,
               payload->>'tenant_id' AS tenant_id_raw
        FROM alert.alert_outbox
        WHERE alert_type = 'CUSTOMER_NOTIFY'
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        tid = str(d.pop("tenant_id_raw") or "")
        out.append(
            {
                "alert_id": str(d.get("alert_id")),
                "created_ts": _iso_ts(d.get("created_ts")),
                "severity": str(d.get("severity") or ""),
                "state": str(d.get("state") or ""),
                "attempt_count": int(d.get("attempt_count") or 0),
                "last_error": (str(d.get("last_error"))[:500] if d.get("last_error") else None),
                "dedupe_key": str(d.get("dedupe_key")) if d.get("dedupe_key") else None,
                "customer_category": str(d.get("customer_category") or ""),
                "tenant_id_masked": mask_tenant_id(tid),
            }
        )
    return out


def fetch_customer_notify_outbox_failed_recent(
    conn: psycopg.Connection[Any], *, limit: int = 30
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 100))
    rows = conn.execute(
        """
        SELECT alert_id, created_ts, state, attempt_count, last_error,
               payload->>'customer_category' AS customer_category,
               payload->>'tenant_id' AS tenant_id_raw
        FROM alert.alert_outbox
        WHERE alert_type = 'CUSTOMER_NOTIFY' AND state = 'failed'
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        tid = str(d.pop("tenant_id_raw") or "")
        out.append(
            {
                "alert_id": str(d.get("alert_id")),
                "created_ts": _iso_ts(d.get("created_ts")),
                "state": str(d.get("state") or ""),
                "attempt_count": int(d.get("attempt_count") or 0),
                "last_error": (str(d.get("last_error"))[:500] if d.get("last_error") else None),
                "customer_category": str(d.get("customer_category") or ""),
                "tenant_id_masked": mask_tenant_id(tid),
            }
        )
    return out


def _mask_chat_id_audit(chat_id: int) -> str:
    s = str(chat_id)
    if len(s) <= 4:
        return "…"
    return f"…{s[-4:]}"


def fetch_telegram_command_audit_recent(
    conn: psycopg.Connection[Any], *, limit: int = 40
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT id, ts, chat_id, user_id, command, args
        FROM alert.command_audit
        ORDER BY ts DESC
        LIMIT %s
        """,
        (lim,),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        cid = d.get("chat_id")
        out.append(
            {
                "id": str(d.get("id")),
                "ts": _iso_ts(d.get("ts")),
                "chat_id_masked": _mask_chat_id_audit(int(cid)) if cid is not None else None,
                "user_id": int(d["user_id"]) if d.get("user_id") is not None else None,
                "command": str(d.get("command") or ""),
                "args": d.get("args"),
            }
        )
    return out
