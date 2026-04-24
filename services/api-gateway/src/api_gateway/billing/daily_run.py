"""Taeglicher Abzug vom Prepaid-Guthaben; Ledger + revisionssichere Alerts."""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import psycopg
import psycopg.errors
from config.gateway_settings import GatewaySettings
from psycopg.types.json import Json
from shared_py.billing_wallet import (
    compute_daily_charge_amount,
    fetch_prepaid_balance_list_usd,
)
from shared_py.customer_telegram_notify import enqueue_customer_notify
from shared_py.subscription_billing_pricing import (
    daily_prorata_net_cents_eur,
    eur_cents_to_list_usd,
)

from api_gateway.db_commerce_queries import insert_usage_ledger_line
from api_gateway.db_customer_portal import adjust_wallet_balance
from api_gateway.db_subscription_billing import (
    ensure_customer_wallet_row,
    insert_subscription_billing_ledger_deduction,
    list_tenants_for_subscription_prepaid_billing,
    set_subscription_suspended_insufficient_funds,
    subscription_ledger_deduction_exists,
)

logger = logging.getLogger("api_gateway.billing")

_EVENT_FLAT = "api_daily_flat_fee"


def _advisory_key(tenant_id: str, accrual_date: date) -> int:
    raw = hashlib.sha256(f"{tenant_id}:{accrual_date.isoformat()}".encode()).hexdigest()[:12]
    return int(raw, 16) % (2**31)


def _advisory_key_subscription_deduction(tenant_id: str, accrual_date: date) -> int:
    raw = (
        hashlib.sha256(
            f"sub_prepaid_deduction:{tenant_id}:{accrual_date.isoformat()}".encode()
        )
        .hexdigest()[:12]
    )
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


_REASON_SUB = "subscription_daily_prepaid_deduction"


def run_daily_billing_cycle(
    conn: psycopg.Connection[Any],
    *,
    settings: GatewaySettings,
    accrual_date: date | None = None,
    tenant_id_filter: str | None = None,
) -> dict[str, Any]:
    r"""
    Taeglicher Abo-Abzug: Plan/Referenzperiode -> Tagesanteil, FX in List-USD.

    Schreibt app.subscription_billing_ledger (DEDUCTION) und bucht wallet; idempotent
    pro Tenant/UTC-Tag. Guthaben fehlt: Status suspended_insufficient_funds (621, 608).
    """
    if not settings.commercial_enabled:
        return {"status": "skipped", "reason": "commercial_disabled"}

    d = accrual_date or datetime.now(timezone.utc).date()
    try:
        raw = (settings.subscription_billing_eur_usd_rate or "1.0").strip() or "1.0"
        eur_to_usd = Decimal(str(raw))
    except Exception:
        eur_to_usd = Decimal("1.0")
    if eur_to_usd < 0:
        eur_to_usd = Decimal("0")

    try:
        rows = list_tenants_for_subscription_prepaid_billing(
            conn, tenant_id_filter=tenant_id_filter
        )
    except Exception as e:
        logger.exception("list_tenants_for_subscription_prepaid_billing")
        return {
            "status": "error",
            "accrual_date": d.isoformat(),
            "reason": str(e)[:500],
        }

    results: list[dict[str, Any]] = []
    for row in rows:
        tid = str(row["tenant_id"])
        idem_ledger = f"subscription:deduct:{d.isoformat()}:{tid}"
        idem_wallet = f"subscription_prepaid:wallet:{d.isoformat()}:{tid}"
        try:
            with conn.transaction():
                conn.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (_advisory_key_subscription_deduction(tid, d),),
                )
                if subscription_ledger_deduction_exists(
                    conn, tenant_id=tid, accrual_date=d
                ):
                    results.append(
                        {
                            "tenant_id": tid,
                            "status": "already_billed",
                            "accrual_date": d.isoformat(),
                        }
                    )
                    continue

                ref_days = int(row["reference_period_days"])
                net_cents = int(row["net_amount_cents"])
                vat_bps = int(row["vat_rate_bps"] or 1900)
                plan = str(row["plan_code"])
                daily_net_cents = daily_prorata_net_cents_eur(
                    net_cents, reference_period_days=ref_days
                )
                charge_list_usd = eur_cents_to_list_usd(
                    daily_net_cents, eur_to_usd_rate=eur_to_usd, quantize="0.00000001"
                )

                ensure_customer_wallet_row(conn, tenant_id=tid)
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

                if charge_list_usd > 0 and bal_before < charge_list_usd:
                    set_subscription_suspended_insufficient_funds(conn, tenant_id=tid)
                    eid = insert_subscription_billing_ledger_deduction(
                        conn,
                        tenant_id=tid,
                        accrual_date=d,
                        plan_code=plan,
                        net_amount_cents_eur=daily_net_cents,
                        amount_list_usd=Decimal("0"),
                        vat_rate_bps=vat_bps,
                        idempotency_key=idem_ledger,
                        meta_json={
                            "outcome": "SUSPENDED_INSUFFICIENT_FUNDS",
                            "balance_before_list_usd": str(bal_before),
                            "required_list_usd": str(charge_list_usd),
                            "eur_to_usd_rate": str(eur_to_usd),
                        },
                    )
                    conn.execute(
                        """
                        INSERT INTO app.customer_portal_audit (
                            tenant_id, action, actor, detail_json
                        )
                        VALUES (%s, 'subscription_billing_suspended', %s, %s::jsonb)
                        """,
                        (
                            tid,
                            "billing_engine:subscription_daily",
                            Json(
                                {
                                    "accrual_date": d.isoformat(),
                                    "plan_code": plan,
                                    "entry_id": str(eid),
                                }
                            ),
                        ),
                    )
                    results.append(
                        {
                            "tenant_id": tid,
                            "status": "suspended_insufficient_funds",
                            "plan_code": plan,
                            "ledger_entry_id": str(eid),
                            "amount_list_usd": "0",
                            "balance_after_list_usd": str(bal_before),
                        }
                    )
                else:
                    if charge_list_usd > 0:
                        adjust_wallet_balance(
                            conn,
                            tenant_id=tid,
                            delta_list_usd=-charge_list_usd,
                            actor="billing_engine:subscription_daily",
                            reason_code=_REASON_SUB,
                            idempotency_key=idem_wallet,
                        )
                    bal_after = fetch_prepaid_balance_list_usd(conn, tenant_id=tid)
                    eid = insert_subscription_billing_ledger_deduction(
                        conn,
                        tenant_id=tid,
                        accrual_date=d,
                        plan_code=plan,
                        net_amount_cents_eur=daily_net_cents,
                        amount_list_usd=charge_list_usd,
                        vat_rate_bps=vat_bps,
                        idempotency_key=idem_ledger,
                        meta_json={
                            "outcome": "charged",
                            "balance_before_list_usd": str(bal_before),
                            "balance_after_list_usd": str(bal_after),
                            "eur_to_usd_rate": str(eur_to_usd),
                        },
                    )
                    conn.execute(
                        """
                        INSERT INTO app.customer_portal_audit (
                            tenant_id, action, actor, detail_json
                        )
                        VALUES (%s, 'subscription_billing_deduction', %s, %s::jsonb)
                        """,
                        (
                            tid,
                            "billing_engine:subscription_daily",
                            Json(
                                {
                                    "accrual_date": d.isoformat(),
                                    "plan_code": plan,
                                    "ledger_entry_id": str(eid),
                                }
                            ),
                        ),
                    )
                    results.append(
                        {
                            "tenant_id": tid,
                            "status": "deducted",
                            "plan_code": plan,
                            "ledger_entry_id": str(eid),
                            "amount_list_usd": str(charge_list_usd),
                            "balance_after_list_usd": str(bal_after),
                        }
                    )
        except Exception as e:
            logger.exception("run_daily_billing_cycle tenant=%s", tid)
            results.append(
                {
                    "tenant_id": tid,
                    "status": "error",
                    "detail": str(e)[:500],
                }
            )
    return {"status": "ok", "accrual_date": d.isoformat(), "results": results}


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
