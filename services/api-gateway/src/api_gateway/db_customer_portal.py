"""Postgres-Helfer: Kundenportal (Profil, Wallet, Zahlungen, Integrations-Status, Audit)."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Json

from api_gateway.db_customer_domain_events import append_customer_domain_event
from api_gateway.db_profit_fee import maybe_apply_hwm_cashflow_for_wallet_reason

_DISPLAY_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def sanitize_display_name(raw: str | None) -> str | None:
    """Keine Steuerzeichen; trim; max 120 Zeichen."""
    if raw is None:
        return None
    s = _DISPLAY_RE.sub("", (raw or "").strip())
    if not s:
        return None
    return s[:120]


def fetch_customer_profile(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, display_name, updated_ts
        FROM app.customer_profile
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("updated_ts") is not None:
        d["updated_ts"] = d["updated_ts"].isoformat()
    return d


def fetch_customer_wallet(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, prepaid_balance_list_usd, updated_ts
        FROM app.customer_wallet
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    d["prepaid_balance_list_usd"] = str(d["prepaid_balance_list_usd"])
    if d.get("updated_ts") is not None:
        d["updated_ts"] = d["updated_ts"].isoformat()
    return d


def fetch_integration_snapshot(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, telegram_state, telegram_hint_public,
               broker_state, broker_hint_public, updated_ts
        FROM app.customer_integration_snapshot
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("updated_ts") is not None:
        d["updated_ts"] = d["updated_ts"].isoformat()
    return d


def fetch_payment_events(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT payment_id, tenant_id, amount_list_usd, currency, status, provider,
               provider_reference_masked, notes_public, created_ts
        FROM app.customer_payment_event
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["payment_id"] = str(d["payment_id"])
        d["amount_list_usd"] = str(d["amount_list_usd"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_portal_audit_recent(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT audit_id, tenant_id, action, actor, detail_json, created_ts
        FROM app.customer_portal_audit
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["audit_id"] = str(d["audit_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_ledger_customer_safe(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    """Ledger-Zeilen ohne meta_json (keine technischen Details ans Frontend)."""
    lim = max(1, min(limit, 200))
    rows = conn.execute(
        """
        SELECT ledger_id, event_type, quantity, unit, unit_price_list_usd,
               line_total_list_usd, created_ts
        FROM app.usage_ledger
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["ledger_id"] = str(d["ledger_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        if d.get("unit_price_list_usd") is not None:
            d["unit_price_list_usd"] = str(d["unit_price_list_usd"])
        d["line_total_list_usd"] = str(d["line_total_list_usd"])
        d["quantity"] = str(d["quantity"])
        out.append(d)
    return out


def update_customer_display_name(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    display_name: str | None,
    actor: str,
    idempotency_key: str | None = None,
) -> None:
    ikey = (idempotency_key or "").strip() or f"profile:display:{uuid4()}"
    inserted, _seq = append_customer_domain_event(
        conn,
        tenant_id=tenant_id,
        aggregate_type="portal",
        event_type="profile_display_name_updated",
        payload={"has_display_name": display_name is not None},
        idempotency_key=ikey[:256],
        correlation_id=None,
        source="gateway",
    )
    if not inserted:
        return
    conn.execute(
        """
        INSERT INTO app.customer_profile (tenant_id, display_name, updated_ts)
        VALUES (%s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            updated_ts = now()
        """,
        (tenant_id, display_name),
    )
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'profile_display_name_updated', %s, %s::jsonb)
        """,
        (tenant_id, actor[:200], Json({"has_display_name": display_name is not None})),
    )


def adjust_wallet_balance(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    delta_list_usd: Decimal,
    actor: str,
    reason_code: str,
    idempotency_key: str | None = None,
) -> str:
    """
    Bucht Delta auf prepaid_wallet. Optional idempotency_key: wiederholter Aufruf
    mit gleichem Key aendert den Saldo nicht erneut (Retry-sicher).
    """
    ikey = (idempotency_key or "").strip() or f"wallet:auto:{uuid4()}"
    inserted, _seq = append_customer_domain_event(
        conn,
        tenant_id=tenant_id,
        aggregate_type="wallet",
        event_type="wallet_adjust",
        payload={
            "delta_list_usd": str(delta_list_usd),
            "reason_code": reason_code[:64],
            "actor": actor[:200],
        },
        idempotency_key=ikey[:256],
        source="gateway",
    )
    if not inserted:
        w = fetch_customer_wallet(conn, tenant_id=tenant_id)
        if w is None:
            raise ValueError("wallet row missing")
        return str(w["prepaid_balance_list_usd"])
    row = conn.execute(
        """
        UPDATE app.customer_wallet
        SET prepaid_balance_list_usd = prepaid_balance_list_usd + %s,
            updated_ts = now()
        WHERE tenant_id = %s
        RETURNING prepaid_balance_list_usd
        """,
        (str(delta_list_usd), tenant_id),
    ).fetchone()
    if row is None:
        raise ValueError("wallet row missing")
    new_bal = str(dict(row)["prepaid_balance_list_usd"])
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'wallet_adjusted', %s, %s::jsonb)
        """,
        (
            tenant_id,
            actor[:200],
            Json({"reason_code": reason_code[:64], "new_balance_list_usd": new_bal}),
        ),
    )
    maybe_apply_hwm_cashflow_for_wallet_reason(
        conn,
        tenant_id=tenant_id,
        delta_list_usd=delta_list_usd,
        reason_code=reason_code,
    )
    return new_bal


def insert_payment_event(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    amount_list_usd: Decimal,
    currency: str,
    status: str,
    provider: str,
    provider_reference_masked: str | None,
    notes_public: str | None,
    actor: str,
) -> UUID:
    row = conn.execute(
        """
        INSERT INTO app.customer_payment_event (
            tenant_id, amount_list_usd, currency, status, provider,
            provider_reference_masked, notes_public
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING payment_id
        """,
        (
            tenant_id,
            str(amount_list_usd),
            currency[:8],
            status[:32],
            provider[:32],
            (provider_reference_masked or "")[:64] or None,
            (notes_public or "")[:500] or None,
        ),
    ).fetchone()
    if row is None:
        raise RuntimeError("insert payment failed")
    pid = UUID(str(dict(row)["payment_id"]))
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'payment_recorded', %s, %s::jsonb)
        """,
        (
            tenant_id,
            actor[:200],
            Json({"payment_id": str(pid), "status": status[:32]}),
        ),
    )
    append_customer_domain_event(
        conn,
        tenant_id=tenant_id,
        aggregate_type="payment",
        event_type="payment_recorded",
        payload={
            "payment_id": str(pid),
            "status": status[:32],
            "amount_list_usd": str(amount_list_usd),
            "provider": provider[:32],
        },
        idempotency_key=f"payment:recorded:{pid}",
        source="gateway",
    )
    return pid


def upsert_integration_snapshot(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    telegram_state: str,
    telegram_hint_public: str | None,
    broker_state: str,
    broker_hint_public: str | None,
    actor: str,
    idempotency_key: str | None = None,
) -> None:
    ikey = (idempotency_key or "").strip() or f"integration:snapshot:{uuid4()}"
    inserted, _seq = append_customer_domain_event(
        conn,
        tenant_id=tenant_id,
        aggregate_type="portal",
        event_type="integration_snapshot_updated",
        payload={
            "telegram_state": telegram_state[:48],
            "broker_state": broker_state[:48],
        },
        idempotency_key=ikey[:256],
        source="gateway",
    )
    if not inserted:
        return
    conn.execute(
        """
        INSERT INTO app.customer_integration_snapshot (
            tenant_id, telegram_state, telegram_hint_public,
            broker_state, broker_hint_public, updated_ts
        )
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            telegram_state = EXCLUDED.telegram_state,
            telegram_hint_public = EXCLUDED.telegram_hint_public,
            broker_state = EXCLUDED.broker_state,
            broker_hint_public = EXCLUDED.broker_hint_public,
            updated_ts = now()
        """,
        (
            tenant_id,
            telegram_state[:48],
            telegram_hint_public,
            broker_state[:48],
            broker_hint_public,
        ),
    )
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'integration_snapshot_updated', %s, '{}'::jsonb)
        """,
        (tenant_id, actor[:200]),
    )


def fetch_portal_identity_security(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT tenant_id, email_verified_at, mfa_totp_enabled,
               password_login_configured, updated_ts
        FROM app.portal_identity_security
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    ev = d.get("email_verified_at")
    d["email_verified_at"] = ev.isoformat() if ev is not None else None
    ut = d.get("updated_ts")
    d["updated_ts"] = ut.isoformat() if ut is not None else None
    return d
