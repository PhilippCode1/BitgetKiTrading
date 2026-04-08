"""
PayPal-Webhook-Stub (Prompt 14) bis direkte PayPal Commerce/Subscriptions angebunden sind.

Authentifizierung: Header ``X-Paypal-Stub-Secret`` (konstantes Shared Secret), nur wenn
``PAYMENT_PAYPAL_STUB_WEBHOOK_ENABLED=true``. Fuer echtes PayPal: Zertifikatskette /
Transmission-Id-Verifikation nach Entwicklerdokumentation nachruesten.

Hinweis: Wiederkehrende PayPal-Abos sind **nicht** identisch mit Einzahlungen ueber
Stripe-Link; separates Produkt-Billing folgt bei Anbindung des PayPal-Subscription-API.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any

import psycopg
from fastapi import HTTPException

from api_gateway.payments.billing_sync import try_insert_rail_webhook_inbox
from config.gateway_settings import GatewaySettings


def process_paypal_stub_webhook(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    body: bytes,
    stub_secret_header: str | None,
) -> dict[str, Any]:
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial disabled")
    if not settings.payment_paypal_stub_webhook_enabled:
        raise HTTPException(status_code=404, detail="paypal stub webhook disabled")
    expected = settings.payment_paypal_stub_webhook_secret.strip()
    if not expected:
        raise HTTPException(status_code=503, detail="paypal stub secret not configured")
    got = (stub_secret_header or "").strip()
    if not secrets.compare_digest(got, expected):
        raise HTTPException(status_code=401, detail="invalid paypal stub secret")

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid json") from None

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid body")

    ev = data.get("event_type") or data.get("eventType") or "unknown"
    rid = data.get("resource") or data.get("id") or data
    fp_raw = json.dumps({"ev": ev, "r": rid}, sort_keys=True, separators=(",", ":"))[:4000]
    fp = f"paypal_stub:{hashlib.sha256(fp_raw.encode()).hexdigest()}"
    meta: dict[str, Any] = {
        "schema_version": "paypal-stub-webhook-v1",
        "event_type": str(ev)[:128],
    }
    if not try_insert_rail_webhook_inbox(conn, rail="paypal_stub", event_fingerprint=fp, meta_json=meta):
        return {"received": True, "rail": "paypal_stub", "duplicate": True}
    return {"received": True, "rail": "paypal_stub", "stored": True}
