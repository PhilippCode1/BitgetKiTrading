"""HMAC-Webhook fuer Prompt-12-Vertragsworkflow (Mock-Provider)."""

from __future__ import annotations

import json

from api_gateway.esign_mock import sign_webhook_body, verify_webhook_signature


def test_verify_webhook_signature_accepts_signed_body() -> None:
    secret = "test-secret-at-least-long-enough-for-hmac"
    body = {
        "provider": "mock",
        "event": "completed",
        "contract_id": "550e8400-e29b-41d4-a716-446655440000",
        "tenant_id": "tenant-a",
        "envelope_id": "env-1",
        "completed_at_unix": 1710000000,
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = sign_webhook_body(secret, body)
    assert verify_webhook_signature(secret, raw, sig)


def test_verify_webhook_signature_rejects_tamper() -> None:
    secret = "test-secret-at-least-long-enough-for-hmac"
    body = {"a": 1, "b": 2}
    sig = sign_webhook_body(secret, body)
    raw2 = json.dumps({"a": 1, "b": 3}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    assert not verify_webhook_signature(secret, raw2, sig)
