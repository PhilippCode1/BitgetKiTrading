"""Abgleich Wallet-Einzahlungen mit Finanz-Ledger (Prompt 13/14), best-effort."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg.types.json import Json

from api_gateway.db_subscription_billing import record_payment_allocation


def sync_wallet_deposit_to_billing_ledger(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    amount_list_usd: Decimal,
    currency: str,
    intent_id: UUID,
    provider: str,
    webhook_provider: str,
) -> None:
    """
    Bucht eine Referenzzeile ins Abo-Finanzjournal (ohne EUR-Brutto: List-USD bleibt in meta).

    Wenn Migration 609 fehlt: still ignorieren.
    """
    try:
        record_payment_allocation(
            conn,
            tenant_id=tenant_id,
            actor=f"deposit_sync:{webhook_provider}",
            amount_gross_cents=None,
            currency="USD",
            meta_json={
                "kind": "wallet_deposit_list_usd",
                "amount_list_usd": str(amount_list_usd),
                "currency": (currency or "USD").upper(),
                "intent_id": str(intent_id),
                "checkout_provider": provider,
            },
        )
    except psycopg.errors.UndefinedTable:
        pass


def try_insert_rail_webhook_inbox(
    conn: psycopg.Connection[Any],
    *,
    rail: str,
    event_fingerprint: str,
    meta_json: dict[str, Any],
) -> bool:
    """True wenn neu; False bei Duplikat."""
    try:
        row = conn.execute(
            """
            INSERT INTO app.payment_rail_webhook_inbox (rail, event_fingerprint, outcome, meta_json)
            VALUES (%s, %s, 'received', %s::jsonb)
            ON CONFLICT (rail, event_fingerprint) DO NOTHING
            RETURNING inbox_id
            """,
            (rail[:32], event_fingerprint[:512], Json(meta_json)),
        ).fetchone()
        return row is not None
    except psycopg.errors.UndefinedTable:
        return True
