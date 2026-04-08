"""Wise-Webhook HMAC-Stub (Prompt 14)."""

from __future__ import annotations

import hashlib
import hmac

from api_gateway.payments.wise_webhook import verify_wise_hmac_sha256_hex


def test_verify_wise_hmac_accepts_valid_hex() -> None:
    secret = "test-secret"
    body = b'{"data":{"id":1},"type":"transfer"}'
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_wise_hmac_sha256_hex(secret, body, sig) is True


def test_verify_wise_hmac_case_insensitive_hex() -> None:
    secret = "s"
    body = b"x"
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest().upper()
    assert verify_wise_hmac_sha256_hex(secret, body, sig) is True


def test_verify_wise_hmac_rejects_tamper() -> None:
    secret = "test-secret"
    body = b'{"ok":true}'
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_wise_hmac_sha256_hex(secret, body + b" ", sig) is False


def test_verify_wise_hmac_rejects_empty() -> None:
    assert verify_wise_hmac_sha256_hex("", b"x", "abc") is False
    assert verify_wise_hmac_sha256_hex("secret", b"x", "") is False
