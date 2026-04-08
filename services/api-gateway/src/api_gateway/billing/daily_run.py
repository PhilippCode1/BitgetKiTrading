"""Taeglicher Abzug vom Prepaid-Guthaben; Ledger + revisionssichere Alerts."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg
import psycopg.errors
from psycopg.types.json import Json

from api_gateway.db_commerce_queries import insert_usage_ledger_line
from api_gateway.db_customer_domain_events import append_customer_domain_event
from api_gateway.db_customer_portal import adjust_wallet_balance
from config.gateway_settings import GatewaySettings
from shared_py.billing_wallet import compute_daily_charge_amount, fetch_prepaid_balance_list_usd
from shared_py.customer_telegram_notify import enqueue_customer_notify

logger = logging.getLogger("api_gateway.billing")

_EVENT_FLAT = "api_daily_flat_fee"


def _advisory_key(tenant_id: str, accrual_date: date) -> int:
    raw = hashlib.sha256(f"{tenant_id}:{accrual_date.isoformat()}".encode()).hexdigest()[:12]
    return int(raw, 16) % (2**31)


def _insert_balance_alert(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    alert_level: str,
    balance_list_usd: Decimal,
    accrual_date: date,
    actor: str,
    extra: dict[str, Any],
) -> bool:
    row = conn.execute(
        """
        INSERT INTO app.billing_balance_alert (
            tenant_id, alert_level, balance_list_usd, accrual_date
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id, alert_level, accrual_date) DO NOTHING
        RETURNING alert_id
        """,
        (tenant_id, alert_level[:16], str(balance_list_usd), accrual_date),
    ).fetchone()
    if row is None:
        return False
    conn.execute(
        """
        INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (
            tenant_id,
            "billing_balance_alert",
            actor[:200],
            Json(
                {
                    "alert_level": alert_level,
                    "balance_list_usd": str(balance_list_usd),
                    "accrual_date": accrual_date.isoformat(),
                    **extra,
                }
            ),
        ),
    )
    return True


def _record_threshold_alert(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    balance_after: Decimal,
    accrual_date: date,
    warning_below: Decimal,
    critical_below: Decimal,
) -> list[str]:
    fired: list[str] = []
    if balance_after <= Decimal("0"):
        level = "depleted"
    elif balance_after <= critical_below:
        level = "critical"
    elif balance_after <= warning_below:
        level = "warning"
    else:
        return fired
    if _insert_balance_alert(
        conn,
        tenant_id=tenant_id,
        alert_level=level,
        balance_list_usd=balance_after,
        accrual_date=accrual_date,
        actor="billing_engine:daily",
        extra={"threshold_rule": "post_daily_charge"},
    ):
        fired.append(level)
    return fired


def _enqueue_balance_customer_notify(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    alert_level: str,
    balance_list_usd: Decimal,
    accrual_date: date,
) -> None:
    bal_s = str(balance_list_usd)
    if alert_level == "depleted":
        text = (
            f"Guthaben aufgebraucht: Ihr Prepaid liegt bei {bal_s} USD (List). "
            "Neue Trades sind blockiert, laufende Positionen werden nicht automatisch geschlossen."
        )
        sev = "critical"
        cat = "balance_depleted"
    elif alert_level == "critical":
        text = (
            f"Guthaben kritisch niedrig ({bal_s} USD List). "
            "Bitte rechtzeitig aufladen, um Unterbrechungen zu vermeiden."
        )
        sev = "warning"
        cat = "balance_critical"
    else:
        text = (
            f"Guthaben niedrig ({bal_s} USD List). "
            "Bitte pruefen Sie Ihr Prepaid im Kundenbereich."
        )
        sev = "info"
        cat = "balance_low"
    enqueue_customer_notify(
        conn,
        tenant_id=tenant_id,
        text=text,
        severity=sev,
        category=cat,
        dedupe_key=f"billing_balance:{tenant_id}:{accrual_date.isoformat()}:{alert_level}",
        audit_actor="billing_engine:daily",
    )


def _list_tenant_ids(
    conn: psycopg.Connection[Any], *, tenant_id_filter: str | None
) -> list[str]:
    if tenant_id_filter:
        tid = tenant_id_filter.strip()
        row = conn.execute(
            "SELECT 1 FROM app.tenant_commercial_state WHERE tenant_id = %s",
            (tid,),
        ).fetchone()
        if row is None:
            return []
        return [tid]
    rows = conn.execute(
        "SELECT tenant_id FROM app.tenant_commercial_state ORDER BY tenant_id"
    ).fetchall()
    return [str(dict(r)["tenant_id"]) for r in rows]


def run_daily_billing(
    conn: psycopg.Connection[Any],
    *,
    settings: GatewaySettings,
    accrual_date: date | None = None,
    tenant_id_filter: str | None = None,
) -> dict[str, Any]:
    if not settings.commercial_enabled:
        return {"status": "skipped", "reason": "commercial_disabled"}

    d = accrual_date or datetime.now(timezone.utc).date()
    daily_fee = Decimal(str(settings.billing_daily_api_fee_usd.strip() or "50"))
    warn_below = Decimal(str(settings.billing_warning_balance_usd.strip() or "100"))
    crit_below = Decimal(str(settings.billing_critical_balance_usd.strip() or "50"))

    results: list[dict[str, Any]] = []
    for tid in _list_tenant_ids(conn, tenant_id_filter=tenant_id_filter):
        try:
            with conn.transaction():
                conn.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (_advisory_key(tid, d),),
                )
                exists = conn.execute(
                    """
                    SELECT 1 FROM app.billing_daily_accrual
                    WHERE tenant_id = %s AND accrual_date = %s
                    """,
                    (tid, d),
                ).fetchone()
                if exists:
                    results.append({"tenant_id": tid, "status": "already_accrued"})
                    continue

                conn.execute(
                    """
                    SELECT prepaid_balance_list_usd
                    FROM app.customer_wallet
                    WHERE tenant_id = %s
                    FOR UPDATE
                    """,
                    (tid,),
                )
                bal_before = fetch_prepaid_balance_list_usd(conn, tenant_id=tid)
                charge = compute_daily_charge_amount(
                    bal_before, daily_fee_usd=daily_fee
                )
                bal_after = bal_before - charge

                if charge > 0:
                    adjust_wallet_balance(
                        conn,
                        tenant_id=tid,
                        delta_list_usd=-charge,
                        actor="billing_engine:daily",
                        reason_code="api_daily_flat_fee",
                    )

                lid = insert_usage_ledger_line(
                    conn,
                    tenant_id=tid,
                    event_type=_EVENT_FLAT,
                    quantity=Decimal("1"),
                    unit="day",
                    unit_price_list_usd=daily_fee,
                    line_total_list_usd=charge,
                    correlation_id=f"billing:{d.isoformat()}",
                    actor="billing_engine:daily",
                    meta_json={
                        "accrual_date": d.isoformat(),
                        "balance_before_list_usd": str(bal_before),
                        "balance_after_list_usd": str(bal_after),
                        "daily_fee_config_usd": str(daily_fee),
                        "charged_usd": str(charge),
                    },
                )

                conn.execute(
                    """
                    INSERT INTO app.billing_daily_accrual (
                        tenant_id, accrual_date,
                        amount_charged_list_usd, balance_before_list_usd,
                        balance_after_list_usd, ledger_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tid,
                        d,
                        str(charge),
                        str(bal_before),
                        str(bal_after),
                        str(lid),
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO app.customer_portal_audit (tenant_id, action, actor, detail_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        tid,
                        "billing_daily_charge_recorded",
                        "billing_engine:daily",
                        Json(
                            {
                                "accrual_date": d.isoformat(),
                                "amount_charged_list_usd": str(charge),
                                "balance_after_list_usd": str(bal_after),
                                "ledger_id": str(lid),
                            }
                        ),
                    ),
                )

                alerts = _record_threshold_alert(
                    conn,
                    tenant_id=tid,
                    balance_after=bal_after,
                    accrual_date=d,
                    warning_below=warn_below,
                    critical_below=crit_below,
                )
                for lvl in alerts:
                    try:
                        _enqueue_balance_customer_notify(
                            conn,
                            tenant_id=tid,
                            alert_level=lvl,
                            balance_list_usd=bal_after,
                            accrual_date=d,
                        )
                    except psycopg.errors.UndefinedTable:
                        pass
                results.append(
                    {
                        "tenant_id": tid,
                        "status": "charged",
                        "amount_charged_list_usd": str(charge),
                        "balance_after_list_usd": str(bal_after),
                        "ledger_id": str(lid),
                        "alerts": alerts,
                    }
                )
        except Exception as e:
            logger.exception("billing daily failed tenant=%s", tid)
            results.append({"tenant_id": tid, "status": "error", "detail": str(e)[:500]})

    return {
        "status": "ok",
        "accrual_date": d.isoformat(),
        "results": results,
    }


def build_billing_status_public(
    *,
    prepaid_balance_list_usd: Decimal,
    daily_fee_usd: Decimal,
    min_new_trade_usd: Decimal,
    warning_below_usd: Decimal,
    critical_below_usd: Decimal,
) -> dict[str, Any]:
    """Oeffentliche Darstellung fuer Kunden-API (keine Secrets)."""
    if prepaid_balance_list_usd <= Decimal("0"):
        level = "depleted"
    elif prepaid_balance_list_usd <= critical_below_usd:
        level = "critical"
    elif prepaid_balance_list_usd <= warning_below_usd:
        level = "warning"
    else:
        level = "ok"
    allows_new_trades = prepaid_balance_list_usd >= min_new_trade_usd
    return {
        "schema_version": "billing-status-v1",
        "prepaid_balance_list_usd": str(prepaid_balance_list_usd),
        "daily_api_fee_list_usd": str(daily_fee_usd),
        "min_balance_new_trade_list_usd": str(min_new_trade_usd),
        "warning_below_list_usd": str(warning_below_usd),
        "critical_below_list_usd": str(critical_below_usd),
        "balance_level": level,
        "allows_new_trades": allows_new_trades,
        "note_de": (
            "Neue Trades werden nur bei ausreichendem Guthaben eroeffnet; "
            "laufende Positionen werden nicht automatisch geschlossen."
        ),
    }
