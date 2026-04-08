"""Prepaid-Guthaben (app.customer_wallet) fuer Trade-Gates und Billing."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg


def fetch_prepaid_balance_list_usd(
    conn: psycopg.Connection[Any], *, tenant_id: str
) -> Decimal:
    row = conn.execute(
        """
        SELECT prepaid_balance_list_usd
        FROM app.customer_wallet
        WHERE tenant_id = %s
        """,
        (tenant_id,),
    ).fetchone()
    if row is None:
        return Decimal("0")
    return Decimal(str(dict(row)["prepaid_balance_list_usd"]))


def prepaid_allows_new_trade(
    balance_list_usd: Decimal, *, min_activation_usd: Decimal
) -> tuple[bool, str]:
    if balance_list_usd >= min_activation_usd:
        return True, ""
    return (
        False,
        f"prepaid_balance_list_usd {balance_list_usd} < min_activation_usd "
        f"{min_activation_usd} (API-Billing)",
    )


def compute_daily_charge_amount(
    balance_list_usd: Decimal, *, daily_fee_usd: Decimal
) -> Decimal:
    """Abzug hoechstens bis 0; nie negatives Wallet."""
    if balance_list_usd <= 0:
        return Decimal("0")
    return min(daily_fee_usd, balance_list_usd)
