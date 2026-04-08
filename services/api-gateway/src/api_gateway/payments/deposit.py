"""Einzahlungs-Flow: Checkout starten, erfolgreiche Zahlung verbuchen."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from fastapi import HTTPException

from api_gateway.db_customer_portal import (
    adjust_wallet_balance,
    insert_payment_event,
)
from api_gateway.db_payment_failure_log import insert_payment_webhook_failure
from api_gateway.db_payment_intents import (
    fetch_intent_by_checkout_session,
    fetch_intent_by_id_any_tenant,
    finalize_intent_success,
    mark_webhook_done,
    try_claim_webhook,
    update_intent_checkout_session,
    update_intent_status,
    upsert_intent_for_checkout,
)
from config.gateway_settings import GatewaySettings
from shared_py.customer_telegram_notify import enqueue_customer_notify

from api_gateway.payments.billing_sync import sync_wallet_deposit_to_billing_ledger
from api_gateway.payments.stripe_checkout import (
    stripe_parse_webhook,
    stripe_session_create,
    stripe_session_retrieve_url,
)


def _mask_ref(ref: str, *, keep: int = 8) -> str:
    r = ref.strip()
    if len(r) <= keep:
        return "***"
    return f"…{r[-keep:]}"


def start_deposit_checkout(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    tenant_id: str,
    idempotency_key: str,
    provider: str,
    amount_list_usd: Decimal,
    currency: str,
) -> dict[str, Any]:
    if not settings.commercial_enabled or not settings.payment_checkout_enabled:
        raise HTTPException(status_code=404, detail="payment checkout disabled")
    env = settings.payment_environment()
    prov = provider.strip().lower()
    if prov not in ("stripe", "mock"):
        raise HTTPException(status_code=400, detail="unsupported provider")

    intent, created = upsert_intent_for_checkout(
        conn,
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        provider=prov,
        environment=env,
        amount_list_usd=amount_list_usd,
        currency=currency.upper()[:8],
    )
    if intent["provider"] != prov:
        raise HTTPException(status_code=409, detail="idempotency key used for different provider")
    if intent["status"] == "succeeded":
        return {
            "intent_id": intent["intent_id"],
            "status": "succeeded",
            "receipt": intent.get("receipt_json") or {},
            "idempotent_replay": True,
        }

    if prov == "mock":
        if not settings.payment_mock_enabled:
            raise HTTPException(status_code=400, detail="mock provider disabled")
        if env == "live":
            raise HTTPException(status_code=400, detail="mock not available in live mode")
        if not settings.payment_mock_webhook_secret.strip():
            raise HTTPException(status_code=503, detail="mock webhook secret not configured")
        update_intent_status(
            conn,
            intent_id=UUID(intent["intent_id"]),
            status="awaiting_payment",
        )
        return {
            "intent_id": intent["intent_id"],
            "status": "awaiting_payment",
            "provider": "mock",
            "environment": env,
            "checkout_url": None,
            "next_step": "POST /v1/commerce/payments/webhooks/mock with X-Payment-Mock-Secret",
        }

    if not settings.payment_stripe_enabled:
        raise HTTPException(status_code=400, detail="stripe disabled")
    if not settings.payment_stripe_secret_key.strip():
        raise HTTPException(status_code=503, detail="stripe not configured")
    try:
        iid = UUID(intent["intent_id"])
        sid, url = stripe_session_create(
            settings,
            intent_id=iid,
            tenant_id=tenant_id,
            amount_list_usd=amount_list_usd,
            currency=currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"stripe error: {e!s}") from e

    update_intent_checkout_session(
        conn,
        intent_id=iid,
        checkout_session_id=sid,
        status="checkout_ready",
    )
    update_intent_status(conn, intent_id=iid, status="awaiting_payment")
    return {
        "intent_id": intent["intent_id"],
        "status": "awaiting_payment",
        "provider": "stripe",
        "environment": env,
        "checkout_url": url,
        "stripe_checkout_session_id_masked": _mask_ref(sid),
    }


def resume_stripe_checkout(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    tenant_id: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """Falls Intent existiert und Stripe-Session noch offen, URL zurueckgeben."""
    if not settings.payment_stripe_enabled:
        return None
    row = conn.execute(
        """
        SELECT * FROM app.payment_deposit_intent
        WHERE tenant_id = %s AND idempotency_key = %s AND provider = 'stripe'
        """,
        (tenant_id, idempotency_key[:128]),
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    if d.get("status") != "awaiting_payment" or not d.get("provider_checkout_session_id"):
        return None
    url = stripe_session_retrieve_url(settings, str(d["provider_checkout_session_id"]))
    if not url:
        return None
    return {
        "intent_id": str(d["intent_id"]),
        "status": "awaiting_payment",
        "checkout_url": url,
        "idempotent_replay": True,
    }


def apply_successful_deposit(
    conn: psycopg.Connection[Any],
    *,
    intent: dict[str, Any],
    webhook_provider: str,
    provider_event_id: str,
    provider_payment_intent_id: str | None,
    receipt_extra: dict[str, Any],
) -> None:
    intent_uuid = UUID(str(intent["intent_id"]))
    tenant_id = str(intent["tenant_id"])

    if not try_claim_webhook(
        conn,
        provider=webhook_provider,
        provider_event_id=provider_event_id,
        intent_id=intent_uuid,
    ):
        return

    locked = conn.execute(
        """
        UPDATE app.payment_deposit_intent
        SET status = 'processing', updated_ts = now()
        WHERE intent_id = %s
          AND status IN ('awaiting_payment', 'checkout_ready', 'created')
        RETURNING *
        """,
        (str(intent_uuid),),
    ).fetchone()
    if locked is None:
        mark_webhook_done(
            conn,
            provider=webhook_provider,
            provider_event_id=provider_event_id,
            outcome="noop_wrong_state_or_done",
        )
        return

    row = dict(locked)
    amount = Decimal(str(row["amount_list_usd"]))
    currency = str(row.get("currency") or "USD")
    prov = str(row.get("provider") or "unknown")
    prior_ok = conn.execute(
        """
        SELECT COUNT(*)::int AS c FROM app.payment_events
        WHERE tenant_id = %s AND status = 'succeeded'
        """,
        (tenant_id,),
    ).fetchone()
    prior_count = int(dict(prior_ok)["c"]) if prior_ok else 0
    receipt: dict[str, Any] = {
        "schema_version": "payment-receipt-v1",
        "intent_id": str(intent_uuid),
        "tenant_id_masked": tenant_id[:4] + "…" if len(tenant_id) > 6 else "***",
        "amount_list_usd": str(amount),
        "currency": currency,
        "provider": prov,
        "paid_at": datetime.now(timezone.utc).isoformat(),
        **receipt_extra,
    }
    try:
        finalize_intent_success(
            conn,
            intent_id=intent_uuid,
            provider_payment_intent_id=provider_payment_intent_id,
            receipt_json=receipt,
        )
        masked = _mask_ref(provider_event_id, keep=12)
        insert_payment_event(
            conn,
            tenant_id=tenant_id,
            amount_list_usd=amount,
            currency=currency,
            status="succeeded",
            provider=prov,
            provider_reference_masked=masked,
            notes_public="Deposit via payment checkout",
            actor=f"webhook:{webhook_provider}",
        )
        adjust_wallet_balance(
            conn,
            tenant_id=tenant_id,
            delta_list_usd=amount,
            actor=f"webhook:{webhook_provider}",
            reason_code="payment_deposit",
        )
        sync_wallet_deposit_to_billing_ledger(
            conn,
            tenant_id=tenant_id,
            amount_list_usd=amount,
            currency=currency,
            intent_id=intent_uuid,
            provider=prov,
            webhook_provider=webhook_provider,
        )
        try:
            enqueue_customer_notify(
                conn,
                tenant_id=tenant_id,
                text=(
                    f"Einzahlung bestaetigt: +{amount} {currency} (Brutto List-USD) "
                    f"wurden gutgeschrieben. Stand siehe Kundenbereich."
                ),
                category="deposit_confirmed",
                severity="info",
                dedupe_key=f"deposit_confirmed:{intent_uuid}",
                audit_actor=f"webhook:{webhook_provider}",
            )
            if prior_count == 0:
                enqueue_customer_notify(
                    conn,
                    tenant_id=tenant_id,
                    text=(
                        "Ihr Kundenkonto ist jetzt finanziell aktiv (erste bestaetigte Einzahlung). "
                        "Bitte Telegram verbinden, falls noch nicht geschehen — vor KI-/Trade-Aktivierung erforderlich."
                    ),
                    category="account_active",
                    severity="info",
                    dedupe_key=f"account_active:{tenant_id}:first_deposit",
                    audit_actor=f"webhook:{webhook_provider}",
                )
        except psycopg.errors.UndefinedTable:
            pass
        mark_webhook_done(
            conn,
            provider=webhook_provider,
            provider_event_id=provider_event_id,
            outcome="succeeded",
        )
    except Exception as ex:
        try:
            insert_payment_webhook_failure(
                conn,
                provider=webhook_provider,
                provider_event_id=provider_event_id,
                intent_id=intent_uuid,
                error_class=type(ex).__name__,
                error_message=str(ex)[:1900],
                meta_json={"phase": "apply_successful_deposit"},
            )
        except psycopg.errors.UndefinedTable:
            pass
        mark_webhook_done(
            conn,
            provider=webhook_provider,
            provider_event_id=provider_event_id,
            outcome="failed_processing",
        )
        update_intent_status(
            conn,
            intent_id=intent_uuid,
            status="failed",
            last_error_public="Settlement failed — contact support with intent id",
        )
        raise


def process_mock_webhook(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    intent_id: UUID,
    mock_secret_header: str | None,
) -> dict[str, Any]:
    if settings.payment_environment() == "live":
        raise HTTPException(status_code=404, detail="mock webhook disabled in live")
    if not settings.payment_mock_enabled:
        raise HTTPException(status_code=404, detail="mock disabled")
    expected = settings.payment_mock_webhook_secret.strip()
    if not expected or not mock_secret_header:
        raise HTTPException(status_code=401, detail="mock secret required")
    if not secrets.compare_digest(mock_secret_header.strip(), expected):
        raise HTTPException(status_code=401, detail="invalid mock secret")

    intent = fetch_intent_by_id_any_tenant(conn, intent_id=intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="intent not found")
    if str(intent.get("provider")) != "mock":
        raise HTTPException(status_code=400, detail="intent is not mock provider")
    if str(intent.get("environment")) == "live":
        raise HTTPException(status_code=400, detail="invalid intent environment")

    event_id = f"mock:{intent_id}"
    apply_successful_deposit(
        conn,
        intent=intent,
        webhook_provider="mock",
        provider_event_id=event_id,
        provider_payment_intent_id=None,
        receipt_extra={"settlement": "mock_sandbox"},
    )
    fresh = fetch_intent_by_id_any_tenant(conn, intent_id=intent_id)
    return {
        "status": "ok",
        "intent_id": str(intent_id),
        "payment_status": str(fresh.get("status")) if fresh else None,
    }


def process_stripe_webhook_payload(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    payload: bytes,
    sig_header: str | None,
) -> dict[str, Any]:
    """Signatur pruefen, checkout.session.completed verbuchen; immer idempotent."""
    if not settings.commercial_enabled or not settings.payment_checkout_enabled:
        raise HTTPException(status_code=404, detail="payment checkout disabled")
    if not settings.payment_stripe_enabled:
        raise HTTPException(status_code=503, detail="stripe disabled")
    try:
        event = stripe_parse_webhook(settings, payload, sig_header)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    et = str(event.get("type") or "")
    eid = str(event.get("id") or "")
    data = event.get("data") or {}
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        return {"received": True, "handled": False, "event_type": et}

    success_types = frozenset(
        {"checkout.session.completed", "checkout.session.async_payment_succeeded"}
    )
    fail_types = frozenset({"checkout.session.async_payment_failed"})

    if et in success_types:
        build_stripe_deposit_from_session(
            conn,
            stripe_event_id=eid or "unknown",
            session_obj=obj,
        )
        return {"received": True, "handled": True, "event_type": et}
    if et in fail_types:
        handle_stripe_checkout_session_async_failed(
            conn,
            stripe_event_id=eid or "unknown",
            session_obj=obj,
        )
        return {"received": True, "handled": True, "event_type": et}
    return {"received": True, "handled": False, "event_type": et}


def build_stripe_deposit_from_session(
    conn: psycopg.Connection[Any],
    *,
    stripe_event_id: str,
    session_obj: dict[str, Any],
) -> None:
    sid = str(session_obj.get("id") or "")
    if not sid:
        return
    if str(session_obj.get("payment_status") or "") != "paid":
        # z. B. Alipay/WeChat: erst async_payment_succeeded verbucht
        return
    intent = fetch_intent_by_checkout_session(conn, checkout_session_id=sid)
    if intent is None:
        return
    meta = session_obj.get("metadata") or {}
    if str(meta.get("intent_id") or "") != str(intent.get("intent_id")):
        return
    pi = session_obj.get("payment_intent")
    pi_s = str(pi) if pi else None
    amount_total = session_obj.get("amount_total")
    receipt_extra: dict[str, Any] = {
        "stripe_checkout_session_id": _mask_ref(sid),
        "payment_method_types": session_obj.get("payment_method_types"),
    }
    if amount_total is not None:
        receipt_extra["amount_total_minor"] = amount_total
    apply_successful_deposit(
        conn,
        intent=intent,
        webhook_provider="stripe",
        provider_event_id=stripe_event_id,
        provider_payment_intent_id=pi_s,
        receipt_extra=receipt_extra,
    )


def handle_stripe_checkout_session_async_failed(
    conn: psycopg.Connection[Any],
    *,
    stripe_event_id: str,
    session_obj: dict[str, Any],
) -> None:
    if not try_claim_webhook(
        conn,
        provider="stripe",
        provider_event_id=stripe_event_id,
        intent_id=None,
    ):
        return
    sid = str(session_obj.get("id") or "")
    if not sid:
        mark_webhook_done(
            conn,
            provider="stripe",
            provider_event_id=stripe_event_id,
            outcome="noop_no_session",
        )
        return
    intent = fetch_intent_by_checkout_session(conn, checkout_session_id=sid)
    if intent is None:
        mark_webhook_done(
            conn,
            provider="stripe",
            provider_event_id=stripe_event_id,
            outcome="noop_no_intent",
        )
        return
    meta = session_obj.get("metadata") or {}
    if str(meta.get("intent_id") or "") != str(intent.get("intent_id")):
        mark_webhook_done(
            conn,
            provider="stripe",
            provider_event_id=stripe_event_id,
            outcome="noop_metadata_mismatch",
        )
        return
    iid = UUID(str(intent["intent_id"]))
    update_intent_status(
        conn,
        intent_id=iid,
        status="failed",
        last_error_public="Async payment failed (e.g. wallet / bank decline)",
    )
    mark_webhook_done(
        conn,
        provider="stripe",
        provider_event_id=stripe_event_id,
        outcome="handled_async_failed",
    )
