from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.orders.models import EmergencyFlattenRequest, OrderCreateRequest, ReduceOnlyOrderRequest
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError
from tests.unit.live_broker.test_private_rest_client import (
    InMemoryOrderRepo,
    _seed_exchange_long_for_reduce_only_guard,
)


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "STRATEGY_EXEC_MODE": "manual",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_REQUIRE_EXECUTION_BINDING": "false",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "false",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "false",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_SYMBOL": "BTCUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
        "BITGET_MARGIN_COIN": "USDT",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def _server_time_response() -> httpx.Response:
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


def test_reduce_only_remains_possible_with_safety_latch(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    _seed_exchange_long_for_reduce_only_guard(repo)
    repo._safety_latch_active = True
    placed: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            body = json.loads(request.content.decode("utf-8"))
            placed.append(body)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "ro-1"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    with patch("live_broker.orders.service.verify_execution_liquidity", return_value=None):
        with pytest.raises(BitgetRestError):
            service.create_order(
                OrderCreateRequest(
                    source_service="manual",
                    symbol="BTCUSDT",
                    side="buy",
                    order_type="limit",
                    size="0.01",
                    price="65000",
                )
            )
        out = service.create_reduce_only_order(
            ReduceOnlyOrderRequest(
                source_service="manual",
                symbol="BTCUSDT",
                side="sell",
                trade_side="close",
                order_type="market",
                size="0.01",
            )
        )
    assert out["ok"] is True
    assert placed[-1]["reduceOnly"] == "YES"


def test_emergency_flatten_remains_possible_for_risk_reduction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_TRADE_ENABLE="false")
    repo = InMemoryOrderRepo()
    placed: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            body = json.loads(request.content.decode("utf-8"))
            placed.append(body)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "flatten-1"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    with patch("live_broker.orders.service.verify_execution_liquidity", return_value=None):
        result = service.emergency_flatten(
            EmergencyFlattenRequest(
                source_service="manual",
                symbol="BTCUSDT",
                side="sell",
                size="0.02",
                reason="panic_button",
            )
        )
    assert result["ok"] is True
    assert placed[-1]["reduceOnly"] == "YES"
