"""Lesende Abfragen fuer Billing-Transparenz (PROMPT 19)."""

from __future__ import annotations

from typing import Any

import psycopg


def fetch_billing_accruals_recent(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT accrual_id, tenant_id, accrual_date, amount_charged_list_usd,
               balance_before_list_usd, balance_after_list_usd, ledger_id, created_ts
        FROM app.billing_daily_accrual
        WHERE tenant_id = %s
        ORDER BY accrual_date DESC, created_ts DESC
        LIMIT %s
        """,
        (tenant_id, max(1, min(limit, 200))),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["accrual_id"] = str(d["accrual_id"])
        for k in (
            "amount_charged_list_usd",
            "balance_before_list_usd",
            "balance_after_list_usd",
        ):
            if d.get(k) is not None:
                d[k] = str(d[k])
        if d.get("ledger_id") is not None:
            d["ledger_id"] = str(d["ledger_id"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out


def fetch_billing_alerts_recent(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT alert_id, tenant_id, alert_level, balance_list_usd, accrual_date, created_ts
        FROM app.billing_balance_alert
        WHERE tenant_id = %s
        ORDER BY created_ts DESC
        LIMIT %s
        """,
        (tenant_id, max(1, min(limit, 200))),
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        d["alert_id"] = str(d["alert_id"])
        if d.get("balance_list_usd") is not None:
            d["balance_list_usd"] = str(d["balance_list_usd"])
        if d.get("created_ts") is not None:
            d["created_ts"] = d["created_ts"].isoformat()
        out.append(d)
    return out
