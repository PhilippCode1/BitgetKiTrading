"""Fehlgeschlagene Webhook-Settlement-Versuche (Prompt 14)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg.types.json import Json


def insert_payment_webhook_failure(
    conn: psycopg.Connection[Any],
    *,
    provider: str,
    provider_event_id: str | None,
    intent_id: UUID | None,
    error_class: str,
    error_message: str,
    meta_json: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO app.payment_webhook_failure_log (
            provider, provider_event_id, intent_id, error_class, error_message, meta_json
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            provider[:64],
            (provider_event_id or "")[:255] or None,
            str(intent_id) if intent_id else None,
            error_class[:128],
            error_message[:2000],
            Json(meta_json or {}),
        ),
    )


def list_payment_webhook_failures_recent(
    conn: psycopg.Connection[Any], *, limit: int = 30
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    try:
        rows = conn.execute(
            """
            SELECT log_id, provider, provider_event_id, intent_id, error_class, error_message,
                   meta_json, created_ts
            FROM app.payment_webhook_failure_log
            ORDER BY created_ts DESC
            LIMIT %s
            """,
            (lim,),
        ).fetchall()
    except psycopg.errors.UndefinedTable:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["log_id"] = str(d["log_id"])
        if d.get("intent_id") is not None:
            d["intent_id"] = str(d["intent_id"])
        ct = d.get("created_ts")
        d["created_ts"] = ct.isoformat() if ct is not None else None
        out.append(d)
    return out


def fetch_payment_rail_inbox_summary(
    conn: psycopg.Connection[Any],
) -> list[dict[str, Any]]:
    """Gruppierung rail/outcome fuer Admin-Diagnose (Migration 610)."""
    try:
        rows = conn.execute(
            """
            SELECT rail, outcome, count(*)::bigint AS cnt
            FROM app.payment_rail_webhook_inbox
            GROUP BY rail, outcome
            ORDER BY rail, outcome
            """
        ).fetchall()
    except psycopg.errors.UndefinedTable:
        return []
    return [
        {"rail": str(r["rail"]), "outcome": str(r["outcome"]), "count": int(r["cnt"])}
        for r in rows
    ]
