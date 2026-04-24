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
from shared_py.modul_mate_db_gates import tenant_has_active_live_commercial_contract

logger = logging.getLogger(__name__)

DEFAULT_HIGH_LEVERAGE_THRESHOLD: float = 5.0

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
    if c in (
        "live_order",
        "order_live",
        "live_fill",
        "live_order_open",
        "live_order_close",
    ):
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


def _base_category_allowed(prefs: dict[str, Any], category: str) -> bool:
    cat = (category or "").strip()
    if cat in _ALWAYS_ALLOW_CATEGORIES:
        return True
    key = _pref_key_for_category(cat)
    if key is None:
        return True
    return bool(prefs.get(key, True))


def signal_notification_routing_allowed(
    prefs: dict[str, Any],
    *,
    category: str,
    trading_mode: str,
    leverage: float | None = None,
    signal_type: str | None = None,
    market_family: str | None = None,
    high_leverage_threshold: float = DEFAULT_HIGH_LEVERAGE_THRESHOLD,
    has_live_commercial_contract: bool = False,
    plan_allows_instrument_family: bool = True,
) -> tuple[bool, str | None]:
    """
    Reine Fachlogik: darf eine strategie-/Signalbezogene Kunden-Benachrichtigung raus.

    - LIVE: zusaetzlich abgeschlossener Vertragsworkflow (admin_review_complete) und
      Plan-Entitlement fuer ``signal_instrument_families`` (sofern gesetzt).
    - Hebel: oberhalb ``high_leverage_threshold`` nur mit ``notify_signal_high_leverage``.
    - Signaltyp: explizit false in ``signal_type_prefs_json`` (Key = z. B. TREND_CONTINUATION) blockt.
    """
    if not _base_category_allowed(prefs, category):
        return False, "category_pref_off"
    m = (trading_mode or "").strip().lower()
    if m == "live":
        if not has_live_commercial_contract:
            return False, "no_active_live_commercial_contract"
        if not plan_allows_instrument_family:
            return False, "instrument_family_not_in_plan"
    if leverage is not None:
        try:
            lv = float(leverage)
        except (TypeError, ValueError):
            lv = 0.0
        if lv > float(high_leverage_threshold) and not bool(
            prefs.get("notify_signal_high_leverage", True)
        ):
            return False, "high_leverage_alerts_disabled"
    st = (signal_type or "").strip().upper()
    if st:
        pmap = prefs.get("signal_type_prefs_json")
        if isinstance(pmap, str):
            try:
                pmap = json.loads(pmap)
            except json.JSONDecodeError:
                pmap = {}
        if not isinstance(pmap, dict):
            pmap = {}
        if st in pmap and not bool(pmap[st]):
            return False, "signal_type_disabled"
    return True, None


def tenant_plan_allows_instrument_family(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    market_family: str | None,
) -> bool:
    """
    Wenn ``entitlements_json.signal_instrument_families`` gesetzt ist, muss die Familie
    enthalten sein; fehlt der Key, alle Familien (Rueckwaertskompat).
    Leere Liste = kein Zugang.
    """
    mf = (market_family or "").strip().lower()
    if not mf:
        return True
    try:
        row = conn.execute(
            """
            SELECT p.entitlements_json
            FROM app.tenant_commercial_state t
            JOIN app.commercial_plan_definitions p ON p.plan_id = t.plan_id
            WHERE t.tenant_id = %s
            """,
            (tenant_id,),
        ).fetchone()
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        return True
    if not row:
        return False
    raw = row.get("entitlements_json")
    if raw is None:
        return True
    if isinstance(raw, str):
        try:
            ej = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return True
    elif isinstance(raw, dict):
        ej = raw
    else:
        return True
    if not isinstance(ej, dict):
        return True
    fams = ej.get("signal_instrument_families")
    if fams is None:
        return True
    if not isinstance(fams, list):
        return True
    if len(fams) == 0:
        return False
    allowed = {str(x).strip().lower() for x in fams if x is not None}
    return mf in allowed


def customer_notify_allowed_by_prefs(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    category: str,
    signal_context: dict[str, Any] | None = None,
) -> bool:
    """
    Prefs-Check. Optional ``signal_context`` (trading_mode, leverage, contract-Flags, …)
    fuer Strategie-Signal-Filter.
    """
    try:
        prefs = fetch_notify_prefs_merged(conn, tenant_id=tenant_id)
    except psycopg.errors.UndefinedTable:
        return True
    if signal_context is None:
        if not _base_category_allowed(prefs, category):
            return False
        return True
    m = (signal_context.get("trading_mode") or "paper").strip().lower()
    hlc = bool(signal_context.get("has_live_commercial_contract", False))
    plf = bool(signal_context.get("plan_allows_instrument_family", True))
    ok, _reason = signal_notification_routing_allowed(
        prefs,
        category=category,
        trading_mode="live" if m == "live" else "paper",
        leverage=signal_context.get("leverage"),  # type: ignore[arg-type]
        signal_type=signal_context.get("signal_type"),  # type: ignore[arg-type]
        market_family=signal_context.get("market_family"),  # type: ignore[arg-type]
        high_leverage_threshold=float(
            signal_context.get("high_leverage_threshold", DEFAULT_HIGH_LEVERAGE_THRESHOLD)
        ),
        has_live_commercial_contract=hlc,
        plan_allows_instrument_family=plf,
    )
    return ok


def dispatch_signal_notification(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    text: str,
    category: str,
    trading_mode: str,
    severity: str = "info",
    dedupe_key: str | None = None,
    audit_actor: str = "signal_notify",
    signal_type: str | None = None,
    leverage: float | None = None,
    market_family: str | None = None,
    high_leverage_threshold: float = DEFAULT_HIGH_LEVERAGE_THRESHOLD,
) -> str | None:
    """
    Zentrale Signal-/Strategie-Benachrichtigung: Prefs, kommerzielle Voraussetzung, dann Outbox.
    """
    m = (trading_mode or "").strip().lower()
    has_contract = True
    if m == "live":
        try:
            has_contract = tenant_has_active_live_commercial_contract(
                conn, tenant_id=tenant_id
            )
        except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
            has_contract = True
    plan_ok = True
    try:
        plan_ok = tenant_plan_allows_instrument_family(
            conn, tenant_id=tenant_id, market_family=market_family
        )
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        plan_ok = True
    ctx: dict[str, Any] = {
        "trading_mode": m,
        "leverage": leverage,
        "signal_type": signal_type,
        "market_family": market_family,
        "high_leverage_threshold": high_leverage_threshold,
        "has_live_commercial_contract": has_contract,
        "plan_allows_instrument_family": plan_ok,
    }
    return enqueue_customer_notify(
        conn,
        tenant_id=tenant_id,
        text=text,
        severity=severity,
        category=category,
        dedupe_key=dedupe_key,
        audit_actor=audit_actor,
        signal_context=ctx,
    )


def enqueue_customer_notify(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    text: str,
    severity: str = "info",
    category: str,
    dedupe_key: str | None = None,
    audit_actor: str = "customer_notify",
    signal_context: dict[str, Any] | None = None,
) -> str | None:
    """
    Fuegt CUSTOMER_NOTIFY in alert.alert_outbox ein. None wenn kein Chat gebunden
    oder Kategorie laut Mandanten-Prefs unterdrueckt.
    """
    if not customer_notify_allowed_by_prefs(
        conn, tenant_id=tenant_id, category=category, signal_context=signal_context
    ):
        logger.info(
            "skip customer notify prefs tenant=%s category=%s signal=%s",
            tenant_id,
            category,
            bool(signal_context),
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
            Json(
                {
                    "alert_id": aid,
                    "category": category,
                    "dedupe_key": dedupe_key,
                }
            ),
        ),
    )
    return aid
