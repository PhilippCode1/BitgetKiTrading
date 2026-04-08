"""Fehlerklassifikation, Retry-Faehigkeit und Backoff-Pfade (ohne echtes Netzwerk)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "BITGET_DEMO_ENABLED": "false",
        "LIVE_BROKER_ENABLED": "true",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
        "LIVE_BROKER_BASE_URL": "https://api.bitget.com",
        "LIVE_BROKER_HTTP_TIMEOUT_SEC": "5",
        "LIVE_BROKER_HTTP_MAX_RETRIES": "1",
        "LIVE_BROKER_HTTP_RETRY_BASE_SEC": "0.01",
        "LIVE_BROKER_HTTP_RETRY_MAX_SEC": "0.02",
        "LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD": "5",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def _time_ok() -> httpx.Response:
    ts = int(time.time() * 1000)
    return httpx.Response(
        200,
        json={
            "code": "00000",
            "msg": "success",
            "requestTime": ts,
            "data": {"serverTime": str(ts)},
        },
    )


def test_timestamp_exchange_code_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    sleeps: list[float] = []
    n = {"place": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _time_ok()
        if request.url.path == "/api/v2/mix/order/place-order":
            n["place"] += 1
            if n["place"] == 1:
                return httpx.Response(
                    200,
                    json={
                        "code": "40005",
                        "msg": "timestamp",
                        "requestTime": int(time.time() * 1000),
                        "data": {},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": "x", "orderId": "1"},
                },
            )
        raise AssertionError(request.url.path)

    client = BitgetPrivateRestClient(
        settings,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda d: sleeps.append(float(d)),
    )
    out = client.place_order(
        {
            "symbol": "BTCUSDT",
            "productType": "USDT-FUTURES",
            "marginMode": "isolated",
            "marginCoin": "USDT",
            "size": "0.01",
            "side": "buy",
            "orderType": "limit",
            "price": "1",
            "force": "gtc",
            "clientOid": "bgai-test-crt-ts",
            "reduceOnly": "NO",
        }
    )
    assert out.attempts == 2
    assert n["place"] == 2
    assert len(sleeps) == 1


def test_validation_exchange_code_not_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, LIVE_BROKER_HTTP_MAX_RETRIES="2")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _time_ok()
        if request.url.path == "/api/v2/mix/order/place-order":
            return httpx.Response(
                200,
                json={
                    "code": "40304",
                    "msg": "validation",
                    "requestTime": int(time.time() * 1000),
                    "data": {},
                },
            )
        raise AssertionError(request.url.path)

    client = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(BitgetRestError) as ei:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "1",
                "force": "gtc",
                "clientOid": "bgai-test-crt-val",
                "reduceOnly": "NO",
            }
        )
    assert ei.value.classification == "validation"
    assert ei.value.retryable is False


def test_http_503_classified_server_and_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, LIVE_BROKER_HTTP_MAX_RETRIES="0")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _time_ok()
        if request.url.path == "/api/v2/mix/order/place-order":
            return httpx.Response(503, text="bad gateway")
        raise AssertionError(request.url.path)

    client = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(BitgetRestError) as ei:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "1",
                "force": "gtc",
                "clientOid": "bgai-test-crt-503",
                "reduceOnly": "NO",
            }
        )
    assert ei.value.classification == "server"
    assert ei.value.retryable is True


def test_duplicate_code_classification(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, LIVE_BROKER_HTTP_MAX_RETRIES="0")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _time_ok()
        if request.url.path == "/api/v2/mix/order/place-order":
            return httpx.Response(
                200,
                json={
                    "code": "01003",
                    "msg": "dup",
                    "requestTime": int(time.time() * 1000),
                    "data": {},
                },
            )
        raise AssertionError(request.url.path)

    client = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    with pytest.raises(BitgetRestError) as ei:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "1",
                "force": "gtc",
                "clientOid": "bgai-test-crt-dup",
                "reduceOnly": "NO",
            }
        )
    assert ei.value.classification == "duplicate"
    assert ei.value.retryable is False
