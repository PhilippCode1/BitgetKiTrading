"""Persistenz fuer Einzahlungs-Intents und Webhook-Idempotenz."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from psycopg.types.json import Json


def _row_intent(row: dict[str, Any]) -> dict[str, Any]:
    d = dict(row)
    d["intent_id"] = str(d["intent_id"])
    d["amount_list_usd"] = str(d["amount_list_usd"])
    if d.get("created_ts") is not None:
        d["created_ts"] = d["created_ts"].isoformat()
    if d.get("updated_ts") is not None:
        d["updated_ts"] = d["updated_ts"].isoformat()
    return d


def upsert_intent_for_checkout(
    conn: psycopg.Connection[Any],
    *,
    tenant_id: str,
    idempotency_key: str,
    provider: str,
    environment: str,
    amount_list_usd: Decimal,
    currency: str,
) -> tuple[dict[str, Any], bool]:
    """INSERT oder bestehender Intent; (row, created_new)."""
    row = conn.execute(
        """
        INSERT INTO app.payment_deposit_intent (
            tenant_id, idempotency_key, provider, environment,
            amount_list_usd, currency, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, 'created')
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        RETURNING *
        """,
        (tenant_id, idempotency_key[:128], provider[:32], environment[:16], str(amount_list_usd), currency[:8]),
    ).fetchone()
    if row is not None:
        return _row_intent(dict(row)), True
    row2 = conn.execute(
        """
        SELECT * FROM app.payment_deposit_intent
        WHERE tenant_id = %s AND idempotency_key = %s
        """,
        (tenant_id, idempotency_key[:128]),
    ).fetchone()
    if row2 is None:
        raise RuntimeError("payment intent missing after conflict")
    return _row_intent(dict(row2)), False


def fetch_intent_by_id(
    conn: psycopg.Connection[Any], *, intent_id: UUID, tenant_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.payment_deposit_intent
        WHERE intent_id = %s AND tenant_id = %s
        """,
        (str(intent_id), tenant_id),
    ).fetchone()
    return _row_intent(dict(row)) if row else None


def fetch_intent_by_id_any_tenant(
    conn: psycopg.Connection[Any], *, intent_id: UUID
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM app.payment_deposit_intent WHERE intent_id = %s",
        (str(intent_id),),
    ).fetchone()
    return _row_intent(dict(row)) if row else None


def list_stripe_intents_awaiting_reconciliation(
    conn: psycopg.Connection[Any], *, tenant_id: str, limit: int = 8
) -> list[dict[str, Any]]:
    """
    Offene oder haengende Stripe-Checkouts, die mit Stripe abgeglichen werden sollen
    (fehlender Webhook).
    """
    lim = max(1, min(int(limit), 32))
    rows = conn.execute(
        """
        SELECT * FROM app.payment_deposit_intent
        WHERE tenant_id = %s
          AND provider = 'stripe'
          AND status IN (
              'awaiting_payment', 'checkout_ready', 'created', 'processing'
          )
          AND provider_checkout_session_id IS NOT NULL
        ORDER BY updated_ts ASC
        LIMIT %s
        """,
        (tenant_id, lim),
    ).fetchall()
    return [_row_intent(dict(r)) for r in rows]


def fetch_intent_by_checkout_session(
    conn: psycopg.Connection[Any], *, checkout_session_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.payment_deposit_intent
        WHERE provider_checkout_session_id = %s
        """,
        (checkout_session_id[:255],),
    ).fetchone()
    return _row_intent(dict(row)) if row else None


def update_intent_checkout_session(
    conn: psycopg.Connection[Any],
    *,
    intent_id: UUID,
    checkout_session_id: str,
    status: str,
) -> None:
    conn.execute(
        """
        UPDATE app.payment_deposit_intent
        SET provider_checkout_session_id = %s,
            status = %s,
            updated_ts = now()
        WHERE intent_id = %s
        """,
        (checkout_session_id[:255], status[:32], str(intent_id)),
    )


def update_intent_status(
    conn: psycopg.Connection[Any],
    *,
    intent_id: UUID,
    status: str,
    last_error_public: str | None = None,
) -> None:
    conn.execute(
        """
        UPDATE app.payment_deposit_intent
        SET status = %s,
            last_error_public = COALESCE(%s, last_error_public),
            updated_ts = now()
        WHERE intent_id = %s
        """,
        (status[:32], last_error_public, str(intent_id)),
    )


def finalize_intent_success(
    conn: psycopg.Connection[Any],
    *,
    intent_id: UUID,
    provider_payment_intent_id: str | None,
    receipt_json: dict[str, Any],
) -> None:
    conn.execute(
        """
        UPDATE app.payment_deposit_intent
        SET status = 'succeeded',
            provider_payment_intent_id = COALESCE(%s, provider_payment_intent_id),
            receipt_json = %s::jsonb,
            last_error_public = NULL,
            updated_ts = now()
        WHERE intent_id = %s AND status <> 'succeeded'
        """,
        (
            provider_payment_intent_id[:128] if provider_payment_intent_id else None,
            Json(receipt_json),
            str(intent_id),
        ),
    )


def try_claim_webhook(
    conn: psycopg.Connection[Any],
    *,
    provider: str,
    provider_event_id: str,
    intent_id: UUID | None,
) -> bool:
    """
    True wenn dieser Webhook jetzt verarbeitet werden darf.

    - Neues Ereignis: INSERT mit outcome ``processing``.
    - Bereits ``succeeded`` oder laeuft ``processing``: False (Idempotenz).
    - Nach ``failed_processing``: erneuter Stripe-/PSP-Versuch darf erneut claimen
      (UPDATE auf ``processing``).
    """
    p = provider[:32]
    e = provider_event_id[:255]
    iid = str(intent_id) if intent_id else None
    try:
        conn.execute(
            """
            INSERT INTO app.payment_webhook_inbox (
                provider, provider_event_id, intent_id, processed_ts, outcome
            )
            VALUES (%s, %s, %s, now(), 'processing')
            """,
            (p, e, iid),
        )
        return True
    except psycopg.errors.UniqueViolation:
        pass

    row = conn.execute(
        """
        SELECT outcome FROM app.payment_webhook_inbox
        WHERE provider = %s AND provider_event_id = %s
        FOR UPDATE
        """,
        (p, e),
    ).fetchone()
    if row is None:
        return False
    o = str(dict(row)["outcome"])
    if o == "succeeded":
        return False
    if o == "processing":
        return False
    if o == "failed_processing":
        upd = conn.execute(
            """
            UPDATE app.payment_webhook_inbox
            SET outcome = 'processing',
                processed_ts = now(),
                intent_id = COALESCE(%s::uuid, intent_id)
            WHERE provider = %s AND provider_event_id = %s AND outcome = 'failed_processing'
            RETURNING inbox_id
            """,
            (iid, p, e),
        ).fetchone()
        return upd is not None
    return False


def mark_webhook_done(
    conn: psycopg.Connection[Any],
    *,
    provider: str,
    provider_event_id: str,
    outcome: str,
) -> None:
    conn.execute(
        """
        UPDATE app.payment_webhook_inbox
        SET outcome = %s, processed_ts = now()
        WHERE provider = %s AND provider_event_id = %s
        """,
        (outcome[:64], provider[:32], provider_event_id[:255]),
    )
