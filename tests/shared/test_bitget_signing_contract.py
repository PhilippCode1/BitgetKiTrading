"""REST-Signatur-Payload und HMAC: deterministisch und Bitget-konform."""

from __future__ import annotations

import os

import pytest

from shared_py.bitget.config import BitgetSettings
from shared_py.bitget.http import (
    build_private_rest_headers,
    build_signature_payload,
    canonical_json_body,
    sign_hmac_sha256_base64,
)


def test_build_signature_payload_order_and_query() -> None:
    p1 = build_signature_payload(
        timestamp_ms=1_700_000_000_000,
        method="POST",
        request_path="/api/v2/mix/order/place-order",
        query_string="symbol=BTCUSDT",
        body='{"a":1}',
    )
    assert p1 == (
        "1700000000000POST/api/v2/mix/order/place-order?symbol=BTCUSDT" '{"a":1}'
    )
    p2 = build_signature_payload(
        timestamp_ms=1,
        method="get",
        request_path="/x",
        query_string="?foo=bar",
        body="",
    )
    assert p2 == "1GET/x?foo=bar"


def test_sign_hmac_is_deterministic_for_fixed_secret_and_payload() -> None:
    s1 = sign_hmac_sha256_base64("secret", "payload")
    s2 = sign_hmac_sha256_base64("secret", "payload")
    assert s1 == s2
    assert len(s1) > 20


def test_canonical_json_body_compact_and_skips_empty() -> None:
    assert canonical_json_body({}) == ""
    assert canonical_json_body({"b": True, "x": 1}) == '{"b":true,"x":1}'
    assert canonical_json_body(None) == ""


def test_build_private_rest_headers_contains_expected_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in list(os.environ.keys()):
        if key.startswith("BITGET_"):
            monkeypatch.delenv(key, raising=False)
    settings = BitgetSettings.model_validate(
        {
            "BITGET_SYMBOL": "BTCUSDT",
            "BITGET_DEMO_ENABLED": "false",
            "BITGET_API_KEY": "ak",
            "BITGET_API_SECRET": "sk",
            "BITGET_API_PASSPHRASE": "pp",
            "BITGET_REST_LOCALE": "en-US",
        }
    )
    body = canonical_json_body({"size": "0.01"})
    payload = build_signature_payload(
        timestamp_ms=1000,
        method="POST",
        request_path="/api/v2/mix/order/place-order",
        query_string="",
        body=body,
    )
    sign = sign_hmac_sha256_base64(settings.effective_api_secret, payload)
    headers = build_private_rest_headers(
        settings,
        timestamp_ms=1000,
        method="POST",
        request_path="/api/v2/mix/order/place-order",
        query_string="",
        body=body,
    )
    assert headers["ACCESS-KEY"] == "ak"
    assert headers["ACCESS-SIGN"] == sign
    assert headers["ACCESS-TIMESTAMP"] == "1000"
    assert headers["ACCESS-PASSPHRASE"] == "pp"
    assert headers["Content-Type"] == "application/json"
