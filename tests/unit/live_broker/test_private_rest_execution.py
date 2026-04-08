from __future__ import annotations

import sys
from pathlib import Path
import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)


def test_bitget_signature_payload_format() -> None:
    from shared_py.bitget import build_signature_payload, sign_hmac_sha256_base64

    ts = 1_700_000_000_000
    body = '{"symbol":"BTCUSDT","size":"1"}'
    pre = build_signature_payload(
        timestamp_ms=ts,
        method="POST",
        request_path="/api/v2/mix/order/place-order",
        query_string="",
        body=body,
    )
    assert pre == f"{ts}POST/api/v2/mix/order/place-order{body}"
    sig = sign_hmac_sha256_base64("unit-test-secret-32chars-minimum!!", pre)
    assert isinstance(sig, str) and len(sig) >= 32


def test_clock_skew_gate_raises() -> None:
    from live_broker.config import LiveBrokerSettings
    from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError

    import os

    os.environ.setdefault("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/x")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("PRODUCTION", "false")
    os.environ.setdefault("EXECUTION_MODE", "paper")
    os.environ.setdefault("LIVE_BROKER_ENABLED", "true")
    os.environ.setdefault("BITGET_SYMBOL", "ETHUSDT")
    os.environ.setdefault("BITGET_MARKET_FAMILY", "futures")
    os.environ.setdefault("BITGET_PRODUCT_TYPE", "USDT-FUTURES")
    s = LiveBrokerSettings()
    c = BitgetPrivateRestClient(s, sleep_fn=lambda _x: None)
    c._server_time_offset_ms = s.live_broker_server_time_max_skew_ms + 10_000
    with pytest.raises(BitgetRestError) as ei:
        c._reject_if_clock_skew_too_large()
    assert ei.value.classification == "clock_skew"
    assert ei.value.exchange_handling() == "non_retryable"


def test_auth_exchange_error_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/x")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "true")
    monkeypatch.setenv("BITGET_SYMBOL", "ETHUSDT")
    monkeypatch.setenv("BITGET_MARKET_FAMILY", "futures")
    monkeypatch.setenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES")
    monkeypatch.setenv("BITGET_API_KEY", "ak")
    monkeypatch.setenv("BITGET_API_SECRET", "sk")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "pp")
    monkeypatch.setenv("LIVE_BROKER_HTTP_MAX_RETRIES", "3")

    from live_broker.config import LiveBrokerSettings
    from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError

    calls: list[str] = []

    def dispatch(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "/api/v2/public/time" in str(request.url):
            return httpx.Response(200, json={"code": "00000", "data": {"serverTime": 1_700_000_000_000}})
        return httpx.Response(200, json={"code": "40003", "msg": "invalid sign"})

    transport = httpx.MockTransport(dispatch)
    settings = LiveBrokerSettings()
    client = BitgetPrivateRestClient(
        settings,
        transport=transport,
        sleep_fn=lambda _x: None,
        now_ms_fn=lambda: 1_700_000_000_000,
    )
    with pytest.raises(BitgetRestError) as ei:
        client.place_order({"symbol": "BTCUSDT", "clientOid": "t"})
    assert ei.value.classification == "auth"
    private_hits = [u for u in calls if "place-order" in u]
    assert len(private_hits) == 1


def test_operator_intervention_map(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/x")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "true")
    monkeypatch.setenv("BITGET_SYMBOL", "ETHUSDT")
    monkeypatch.setenv("BITGET_MARKET_FAMILY", "futures")
    monkeypatch.setenv("BITGET_PRODUCT_TYPE", "USDT-FUTURES")
    monkeypatch.setenv("BITGET_API_KEY", "ak")
    monkeypatch.setenv("BITGET_API_SECRET", "sk")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "pp")

    from live_broker.config import LiveBrokerSettings
    from live_broker.private_rest import BitgetPrivateRestClient

    c = BitgetPrivateRestClient(LiveBrokerSettings(), sleep_fn=lambda _x: None)
    exc = c._map_error(
        http_status=200,
        payload={"code": "40007", "msg": "restricted"},
        fallback_message="t",
    )
    assert exc.classification == "operator_intervention"
    assert exc.exchange_handling() == "operator_intervention"


def test_bitget_rest_error_scrubs_payload() -> None:
    from live_broker.private_rest import BitgetRestError

    exc = BitgetRestError(
        classification="validation",
        message="x",
        retryable=False,
        payload={"nested": {"apiSecret": "nope", "ok": 1}},
    )
    d = exc.to_dict()
    assert d["payload"]["nested"]["apiSecret"] == "[REDACTED]"
    assert d["payload"]["nested"]["ok"] == 1


def test_client_oid_idempotent_shape() -> None:
    from uuid import UUID

    from live_broker.orders.service import client_oid_for_internal_order

    u = UUID("12345678-1234-5678-1234-567812345678")
    a = client_oid_for_internal_order("bgai", action_tag="crt", internal_order_id=u)
    b = client_oid_for_internal_order("bgai", action_tag="crt", internal_order_id=u)
    assert a == b
    assert len(a) <= 50
