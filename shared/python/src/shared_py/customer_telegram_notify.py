"""Kunden-Telegram via alert.alert_outbox (Retry/Fehler in alert-engine)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import psycopg
from psycopg.types.json import Json

from shared_py.customer_telegram_prefs import fetch_notify_prefs_merged
from shared_py.customer_telegram_repo import get_chat_id_for_tenant

logger = logging.getLogger(__name__)

# Immer zustellen (Onboarding, Sicherheit, Verknüpfung, manueller Test).
_ALWAYS_ALLOW_CATEGORIES = frozenset(
    {
        "account_active",
        "telegram_link_ok",
        "telegram_test",
        "test",
        "security",
    }
)


def _pref_key_for_category(category: str) -> str | None:
    c = (category or "").strip().lower()
    if c in (
        "paper_order_open",
        "paper_order_close",
        "paper_order_partial",
        "demo_trade",
        "order_paper",
    ):
        return "notify_orders_demo"
    if c in ("live_order", "order_live", "live_fill", "live_order_open", "live_order_close"):
        return "notify_orders_live"
    if c in (
        "deposit_confirmed",
        "balance_low",
        "balance_critical",
        "balance_depleted",
        "billing_notice",
        "subscription_invoice",
        "invoice_issued",
    ):
        return "notify_billing"
    if "contract" in c:
        return "notify_contract"
    if c in ("risk_warning", "trades_blocked"):
        return "notify_risk"
    if c in ("ai_tip", "ki_summary", "customer_assist_hint"):
        return "notify_ai_tip"
    return None


def customer_notify_allowed_by_prefs(
    conn: psycopg.Connection[Any], *, tenant_id: str, category: str
) -> bool:
    cat = (category or "").strip()
    if cat in _ALWAYS_ALLOW_CATEGORIES:
        return True
    key = _pref_key_for_category(cat)
    if key is None:
        return True
    try:
        prefs = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
    except psycopg.errors.UndefinedTable:
        return True
    return bool(prefs.get(key, True))


def enqueue_customer_notify(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    text: str,
    severity: str = "info",
    category: str,
    dedupe_key: str | None = None,
    audit_actor: str = "customer_notify",
) -> str | None:
    """
    Fuegt CUSTOMER_NOTIFY in alert.alert_outbox ein. None wenn kein Chat gebunden
    oder Kategorie laut Mandanten-Prefs unterdrueckt.
    """
    if not customer_notify_allowed_by_prefs(conn, tenant_id=tenant_id, category=category):
        logger.info(
            "skip customer notify prefs tenant=%s category=%s",
            tenant_id,
            category,
        )
        return None
    chat_id = get_chat_id_for_tenant(conn, tenant_id=tenant_id)
    if chat_id is None:
        logger.info(
            "skip customer notify no chat tenant=%s category=%s",
            tenant_id,
            category,
        )
        return None
    sev = (severity or "info").strip().lower()
    if sev == "warning":
        sev = "warn"
    if sev not in ("info", "warn", "critical"):
        sev = "info"
    aid = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "text": text[:3500],
        "customer_category": category[:64],
        "tenant_id": tenant_id[:128],
    }
    conn.execute(
        """
        INSERT INTO alert.alert_outbox (
            alert_id, alert_type, severity, symbol, timeframe, dedupe_key,
            payload, chat_id, state
        )
        VALUES (%s, 'CUSTOMER_NOTIFY', %s, NULL, NULL, %s, %s::jsonb, %s, 'pending')
        """,
        (
            aid,
            sev,
            dedupe_key[:500] if dedupe_key else None,
            json.dumps(payload),
            chat_id,
        ),
    )
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, 'telegram_notify_enqueued', %s, %s::jsonb)
        """,
        (
            tenant_id,
            audit_actor[:200],
            Json({"alert_id": aid, "category": category, "dedupe_key": dedupe_key}),
        ),
    )
    return aid
