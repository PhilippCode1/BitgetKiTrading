"""DB-Helfer: Telegram-Kundenverknuepfung (Pending-Link + Binding)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

import psycopg
from psycopg.types.json import Json


def sha256_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LinkStartResult(TypedDict, total=False):
    ok: bool
    tenant_id: str
    error: str


def create_pending_link(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    ttl_hours: int = 24,
) -> tuple[str, datetime]:
    """Gibt (klartext_token, expires_at_utc) zurueck."""
    token = secrets.token_urlsafe(24)
    exp = datetime.now(timezone.utc) + timedelta(hours=max(1, min(ttl_hours, 168)))
    h = sha256_token(token)
    conn.execute(
        """
        INSERT INTO app.telegram_link_pending (tenant_id, token_sha256, expires_ts)
        VALUES (%s, %s, %s)
        """,
        (tenant_id, h, exp),
    )
    return token, exp


def get_binding_row(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, telegram_chat_id, telegram_username, verified_ts, updated_ts
        FROM app.customer_telegram_binding
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    return dict(row) if row else None


def get_chat_id_for_tenant(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> int | None:
    row = conn.execute(
        "SELECT telegram_chat_id FROM app.customer_telegram_binding WHERE tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    return int(dict(row)["telegram_chat_id"])


def get_tenant_id_for_chat(
    conn: psycopg.Connection[Any], *, telegram_chat_id: int
) -> str | None:
    row = conn.execute(
        "SELECT tenant_id FROM app.customer_telegram_binding WHERE telegram_chat_id = %s",
        (telegram_chat_id,),
    ).fetchone()
    if row is None:
        return None
    return str(dict(row)["tenant_id"])


def mask_chat_id(chat_id: int) -> str:
    s = str(chat_id)
    if len(s) <= 4:
        return "…"
    return f"…{s[-4:]}"


def try_complete_customer_start_link(
    conn: psycopg.Connection[Any],
    *,
    start_arg: str,
    telegram_chat_id: int,
    telegram_username: str | None,
) -> LinkStartResult:
    """
    Verarbeitet Payload nach /start (ohne fuehrendes /).
    Erwartet ``link_<token>`` (Klartext-Token wie von create_pending_link).
    """
    raw = start_arg.strip()
    if not raw.lower().startswith("link_"):
        return LinkStartResult(ok=False, error="not_link_flow")
    token = raw[5:].strip()
    if not token:
        return LinkStartResult(ok=False, error="empty_token")
    h = sha256_token(token)
    row = conn.execute(
        """
        SELECT pending_id, tenant_id, expires_ts, consumed_ts
        FROM app.telegram_link_pending
        WHERE token_sha256 = %s
        """,
        (h,),
    ).fetchone()
    if row is None:
        return LinkStartResult(ok=False, error="unknown_token")
    d = dict(row)
    if d.get("consumed_ts") is not None:
        return LinkStartResult(ok=False, error="token_used")
    exp = d["expires_ts"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        return LinkStartResult(ok=False, error="expired")

    tenant_id = str(d["tenant_id"])
    other = conn.execute(
        """
        SELECT tenant_id FROM app.customer_telegram_binding
        WHERE telegram_chat_id = %s AND tenant_id <> %s
        """,
        (telegram_chat_id, tenant_id),
    ).fetchone()
    if other is not None:
        return LinkStartResult(ok=False, error="chat_bound_other_tenant")

    conn.execute(
        """
        UPDATE app.telegram_link_pending
        SET consumed_ts = now()
        WHERE token_sha256 = %s AND consumed_ts IS NULL
        """,
        (h,),
    )
    conn.execute(
        """
        INSERT INTO app.customer_telegram_binding (
            tenant_id, telegram_chat_id, telegram_username, verified_ts, updated_ts
        )
        VALUES (%s, %s, %s, now(), now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            telegram_chat_id = EXCLUDED.telegram_chat_id,
            telegram_username = EXCLUDED.telegram_username,
            verified_ts = now(),
            updated_ts = now()
        """,
        (tenant_id, telegram_chat_id, telegram_username),
    )
    hint = f"@{telegram_username}" if telegram_username else "Telegram verbunden"
    conn.execute(
        """
        INSERT INTO app.customer_integration_snapshot (
            tenant_id, telegram_state, telegram_hint_public,
            broker_state, broker_hint_public, updated_ts
        )
        VALUES (%s, 'connected', %s, 'unknown', NULL, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            telegram_state = 'connected',
            telegram_hint_public = EXCLUDED.telegram_hint_public,
            updated_ts = now()
        """,
        (tenant_id, hint[:500]),
    )
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'telegram_customer_linked', 'telegram_bot', %s::jsonb)
        """,
        (
            tenant_id,
            Json({"telegram_chat_id_masked": mask_chat_id(telegram_chat_id)}),
        ),
    )
    ensure_alert_chat_allowed(conn, telegram_chat_id=telegram_chat_id)
    return LinkStartResult(ok=True, tenant_id=tenant_id)


def ensure_alert_chat_allowed(conn: psycopg.Connection[Any], *, telegram_chat_id: int) -> None:
    conn.execute(
        """
        INSERT INTO alert.chat_subscriptions (chat_id, status)
        VALUES (%s, 'allowed')
        ON CONFLICT (chat_id) DO UPDATE SET
            status = CASE
                WHEN alert.chat_subscriptions.status = 'blocked' THEN 'blocked'
                ELSE 'allowed'
            END
        """,
        (telegram_chat_id,),
    )


def is_telegram_connected(conn: psycopg.Connection[Any], *, tenant_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM app.customer_telegram_binding WHERE tenant_id = %s",
        (tenant_id,),
    ).fetchone()
    return row is not None


def fetch_tenant_customer_lifecycle_minimal(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    """Kurzinfo fuer Bot /konto; None wenn Tabelle fehlt oder keine Zeile."""
    try:
        row = conn.execute(
            """
            SELECT lifecycle_status, trial_ends_at, email_verified, updated_ts
            FROM app.tenant_customer_lifecycle
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    return dict(row) if row else None
