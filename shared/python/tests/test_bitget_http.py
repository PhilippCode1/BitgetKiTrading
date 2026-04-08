from __future__ import annotations

import base64
import hashlib
import hmac

from shared_py.bitget import (
    BitgetSettings,
    build_private_rest_headers,
    build_query_string,
    build_signature_payload,
    canonical_json_body,
    sign_hmac_sha256_base64,
)


def test_build_signature_payload_matches_official_bitget_shape() -> None:
    body = canonical_json_body(
        {
            "productType": "usdt-futures",
            "symbol": "BTCUSDT",
            "size": "8",
            "marginMode": "crossed",
            "side": "buy",
            "orderType": "limit",
            "clientOid": "channel#123456",
        }
    )
    payload = build_signature_payload(
        timestamp_ms=16273667805456,
        method="POST",
        request_path="/api/v2/mix/order/place-order",
        body=body,
    )
    assert (
        payload
        == '16273667805456POST/api/v2/mix/order/place-order{"productType":"usdt-futures","symbol":"BTCUSDT","size":"8","marginMode":"crossed","side":"buy","orderType":"limit","clientOid":"channel#123456"}'
    )


def test_sign_hmac_sha256_base64_matches_standard_library() -> None:
    payload = "1700000000000GET/api/v2/mix/order/detail?symbol=BTCUSDT&productType=USDT-FUTURES"
    expected = base64.b64encode(
        hmac.new(b"secret", payload.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    assert sign_hmac_sha256_base64("secret", payload) == expected


def test_build_private_rest_headers_uses_effective_demo_credentials() -> None:
    settings = BitgetSettings.model_validate(
        {
            "BITGET_SYMBOL": "BTCUSDT",
            "BITGET_DEMO_ENABLED": True,
            "BITGET_DEMO_API_KEY": "demo-key",
            "BITGET_DEMO_API_SECRET": "demo-secret",
            "BITGET_DEMO_API_PASSPHRASE": "demo-pass",
            "BITGET_REST_LOCALE": "en-US",
        }
    )
    query_string = build_query_string(
        [("symbol", "BTCUSDT"), ("productType", "USDT-FUTURES")]
    )
    headers = build_private_rest_headers(
        settings,
        timestamp_ms=1700000000000,
        method="GET",
        request_path="/api/v2/mix/order/detail",
        query_string=query_string,
    )
    assert headers["ACCESS-KEY"] == "demo-key"
    assert headers["ACCESS-PASSPHRASE"] == "demo-pass"
    assert headers["locale"] == "en-US"
    assert headers["paptrading"] == "1"
    assert headers["ACCESS-SIGN"]
