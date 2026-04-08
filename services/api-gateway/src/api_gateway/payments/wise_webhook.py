"""
Wise Webhook-Eingang (Prompt 14).

Hinweis: Wise dokumentiert Signatur/Header je nach Produktgeneration — dieser Eingang
nutzt optional HMAC-SHA256(hex) ueber den Rohbody mit ``PAYMENT_WISE_WEBHOOK_SECRET``.
Vor Produktivgang mit https://api-docs.wise.com abgleichen und ggf. auf die offizielle
Signaturpruefung umstellen.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import psycopg
from fastapi import HTTPException

from api_gateway.payments.billing_sync import try_insert_rail_webhook_inbox
from config.gateway_settings import GatewaySettings


def verify_wise_hmac_sha256_hex(secret: str, body: bytes, signature_hex: str) -> bool:
    if not secret or not signature_hex:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.strip().lower(), signature_hex.strip().lower())


def _fingerprint_from_wise_body(data: dict[str, Any]) -> str:
    """Stabile Fingerabdruck-Zeile fuer Idempotenz (ohne Rohbody-Secrets)."""
    d = data.get("data")
    if isinstance(d, dict):
        rid = d.get("resource") or d.get("id") or d.get("profile")
        occ = d.get("occurredAt") or d.get("currentState")
        if rid is not None and occ is not None:
            return f"wise:{rid}:{occ}"
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"))[:2000]
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"wise:sha256:{h}"


def process_wise_webhook(
    conn: psycopg.Connection[Any],
    settings: GatewaySettings,
    *,
    body: bytes,
    signature_header: str | None,
) -> dict[str, Any]:
    if not settings.commercial_enabled:
        raise HTTPException(status_code=404, detail="commercial disabled")
    if not settings.payment_wise_webhook_enabled:
        raise HTTPException(status_code=404, detail="wise webhook disabled")
    secret = settings.payment_wise_webhook_secret.strip()
    if not secret:
        raise HTTPException(status_code=503, detail="wise webhook secret not configured")
    sig = (signature_header or "").strip()
    if not verify_wise_hmac_sha256_hex(secret, body, sig):
        raise HTTPException(status_code=401, detail="invalid wise signature")

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="invalid json") from None

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="invalid body")

    fp = _fingerprint_from_wise_body(data)
    meta = {"schema_version": "wise-webhook-v1", "keys": list(data.keys())[:24]}
    if not try_insert_rail_webhook_inbox(conn, rail="wise", event_fingerprint=fp, meta_json=meta):
        return {"received": True, "rail": "wise", "duplicate": True}
    return {"received": True, "rail": "wise", "stored": True}
