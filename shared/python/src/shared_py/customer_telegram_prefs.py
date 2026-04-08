"""Persistierte Telegram-Benachrichtigungs-Präferenzen pro Tenant (Prompt 19)."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Json


DEFAULT_PREFS: dict[str, bool] = {
    "notify_orders_demo": True,
    "notify_orders_live": True,
    "notify_billing": True,
    "notify_contract": True,
    "notify_risk": True,
    "notify_ai_tip": False,
}

_PREF_KEYS = frozenset(DEFAULT_PREFS.keys())


def fetch_notify_prefs_merged(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> dict[str, bool]:
    """Liest Zeile oder liefert DEFAULT_PREFS (keine Zeile = Defaults)."""
    row = conn.execute(
        """
        SELECT notify_orders_demo, notify_orders_live, notify_billing,
               notify_contract, notify_risk, notify_ai_tip
        FROM app.customer_telegram_notify_prefs
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return dict(DEFAULT_PREFS)
    d = dict(row)
    return {k: bool(d[k]) for k in DEFAULT_PREFS}


def upsert_notify_prefs(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    notify_orders_demo: bool | None = None,
    notify_orders_live: bool | None = None,
    notify_billing: bool | None = None,
    notify_contract: bool | None = None,
    notify_risk: bool | None = None,
    notify_ai_tip: bool | None = None,
) -> dict[str, bool]:
    """Schreibt nur übergebene Felder; übrige bleiben aus bestehender Zeile oder Default."""
    cur = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
    for k in _PREF_KEYS:
        v = locals().get(k)
        if v is not None:
            cur[k] = bool(v)
    conn.execute(
        """
        INSERT INTO app.customer_telegram_notify_prefs (
            tenant_id, notify_orders_demo, notify_orders_live, notify_billing,
            notify_contract, notify_risk, notify_ai_tip, updated_ts
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (tenant_id) DO UPDATE SET
            notify_orders_demo = EXCLUDED.notify_orders_demo,
            notify_orders_live = EXCLUDED.notify_orders_live,
            notify_billing = EXCLUDED.notify_billing,
            notify_contract = EXCLUDED.notify_contract,
            notify_risk = EXCLUDED.notify_risk,
            notify_ai_tip = EXCLUDED.notify_ai_tip,
            updated_ts = now()
        """,
        (
            tenant_id,
            cur["notify_orders_demo"],
            cur["notify_orders_live"],
            cur["notify_billing"],
            cur["notify_contract"],
            cur["notify_risk"],
            cur["notify_ai_tip"],
        ),
    )
    return cur


def audit_prefs_changed(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    actor: str,
    detail: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'telegram_notify_prefs_updated', %s, %s::jsonb)
        """,
        (tenant_id, actor[:200], Json(detail)),
    )
