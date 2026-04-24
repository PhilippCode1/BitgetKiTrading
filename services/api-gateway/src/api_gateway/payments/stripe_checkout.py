"""Stripe Checkout Session (serverseitig, kein Publishable Key im Browser noetig fuer Redirect-Flow)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

import stripe
from stripe import SignatureVerificationError, StripeError

from config.gateway_settings import GatewaySettings


def stripe_session_create(
    settings: GatewaySettings,
    *,
    intent_id: UUID,
    tenant_id: str,
    amount_list_usd: Decimal,
    currency: str,
) -> tuple[str, str]:
    """(session_id, checkout_url)."""
    secret = settings.payment_stripe_secret_key.strip()
    if not secret:
        raise RuntimeError("stripe secret missing")
    stripe.api_key = secret
    types = [x.strip() for x in settings.payment_stripe_method_types.split(",") if x.strip()]
    if not types:
        types = ["card"]
    cur = (currency or "USD").lower()
    cents = int((amount_list_usd * Decimal("100")).quantize(Decimal("1")))
    if cents < 50:
        raise ValueError("amount below Stripe minimum for typical currencies")
    success = settings.payment_stripe_success_url.strip()
    cancel = settings.payment_stripe_cancel_url.strip()
    if not success or not cancel:
        raise ValueError("PAYMENT_STRIPE_SUCCESS_URL and PAYMENT_STRIPE_CANCEL_URL required")
    joiner = "&" if "?" in success else "?"
    success_url = f"{success}{joiner}session_id={{CHECKOUT_SESSION_ID}}"
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": cur,
                    "unit_amount": cents,
                    "product_data": {"name": "Account deposit"},
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel,
        metadata={
            "tenant_id": tenant_id,
            "intent_id": str(intent_id),
        },
        payment_method_types=types[:8],
    )
    sid = str(session.id)
    url = str(session.url or "")
    if not url:
        raise RuntimeError("stripe session without url")
    return sid, url


def stripe_checkout_session_idempotency_fingerprint(*, session_id: str) -> str:
    """
    Ein fachlicher Fingerprint pro Checkout (nicht pro Stripe-Event-Id), damit
    Webhook, Retries und GET-Reconciliation nicht doppelt verbuchen.
    """
    sid = (session_id or "").strip()
    if not sid:
        raise ValueError("checkout session id fehlt")
    return f"stripe:checkout_paid:{sid[:255]}"


def retrieve_checkout_session_for_reconciliation(
    settings: GatewaySettings, *, session_id: str
) -> dict[str, Any] | None:
    """Aktuellen Zahlungsstatus der Session abfragen (fuer Balance-Reconciliation)."""
    secret = settings.payment_stripe_secret_key.strip()
    if not secret:
        return None
    stripe.api_key = secret
    try:
        s = stripe.checkout.Session.retrieve((session_id or "")[:255])
    except StripeError:
        return None
    if hasattr(s, "to_dict_recursive"):
        d = s.to_dict_recursive()  # type: ignore[no-untyped-call]
        if isinstance(d, dict):
            return d
    try:
        out = dict(s)  # type: ignore[arg-type]
        if isinstance(out, dict):
            return out
    except Exception:
        pass
    return None


def stripe_session_retrieve_url(settings: GatewaySettings, session_id: str) -> str | None:
    secret = settings.payment_stripe_secret_key.strip()
    if not secret:
        return None
    stripe.api_key = secret
    try:
        s = stripe.checkout.Session.retrieve(session_id)
    except StripeError:
        return None
    if str(getattr(s, "status", "")) == "open" and s.url:
        return str(s.url)
    return None


def stripe_parse_webhook(
    settings: GatewaySettings,
    payload: bytes,
    sig_header: str | None,
) -> dict[str, Any]:
    wh = settings.payment_stripe_webhook_secret.strip()
    if not wh:
        raise RuntimeError("webhook secret missing")
    if not sig_header:
        raise ValueError("missing signature")
    try:
        ev = stripe.Webhook.construct_event(payload, sig_header, wh)
    except ValueError as e:
        raise ValueError("invalid payload") from e
    except SignatureVerificationError as e:
        raise ValueError("invalid signature") from e
    if isinstance(ev, dict):
        return ev
    if hasattr(ev, "to_dict_recursive"):
        return ev.to_dict_recursive()  # type: ignore[no-any-return]
    try:
        return dict(ev)  # type: ignore[arg-type]
    except Exception as e:
        raise ValueError("unexpected stripe event shape") from e
