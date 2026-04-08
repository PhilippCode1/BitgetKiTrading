from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
for p in (REPO_ROOT, LIVE_BROKER_SRC):
    ps = str(p)
    if ps not in sys.path:
        sys.path.insert(0, ps)

from live_broker.config import LiveBrokerSettings
from live_broker.control_plane.models import ControlPlaneReadHistoryRequest
from live_broker.control_plane.service import BitgetControlPlaneService
from live_broker.private_rest import BitgetPrivateRestClient


class _Repo:
    def record_audit_trail(self, record: dict) -> dict:
        return dict(record)


def _settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for key, value in {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "true",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
        "BITGET_MARGIN_COIN": "USDT",
        "LIVE_BROKER_BASE_URL": "https://api.bitget.com",
        "LIVE_BROKER_HTTP_TIMEOUT_SEC": "5",
        "LIVE_BROKER_HTTP_MAX_RETRIES": "0",
        "LIVE_BROKER_SERVER_TIME_SYNC_SEC": "5",
        "LIVE_BROKER_SERVER_TIME_MAX_SKEW_MS": "5000",
    }.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def test_list_orders_history_hits_mix_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/api/v2/public/time":
            ts = int(time.time() * 1000)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "data": {"serverTime": str(ts)},
                    "requestTime": ts,
                },
            )
        if request.url.path == "/api/v2/mix/order/orders-history":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"entrustedList": []},
                },
            )
        raise AssertionError(request.url.path)

    priv = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    out = priv.list_orders_history(params={"limit": "5"}, market_family="futures")
    assert out.request_path == "/api/v2/mix/order/orders-history"
    assert "/api/v2/mix/order/orders-history" in seen


def test_control_plane_read_orders_history_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch)
    audits: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            ts = int(time.time() * 1000)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "data": {"serverTime": str(ts)},
                    "requestTime": ts,
                },
            )
        if request.url.path == "/api/v2/mix/order/orders-history":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"entrustedList": []},
                },
            )
        raise AssertionError(request.url.path)

    class Repo:
        def record_audit_trail(self, record: dict) -> dict:
            audits.append(record)
            return record

    priv = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    svc = BitgetControlPlaneService(settings, priv, Repo())  # type: ignore[arg-type]
    svc.read_orders_history(
        ControlPlaneReadHistoryRequest(limit=10, operator_jti="jti-test", audit_note="unit")
    )
    assert any(a.get("action") == "orders_history_ok" for a in audits)
