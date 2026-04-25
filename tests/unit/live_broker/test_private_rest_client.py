from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from live_broker.config import LiveBrokerSettings
from live_broker.orders.models import (
    EmergencyFlattenRequest,
    KillSwitchRequest,
    OrderCancelRequest,
    OrderCreateRequest,
    OrderQueryRequest,
    OrderReplaceRequest,
    ReduceOnlyOrderRequest,
    SafetyLatchReleaseRequest,
)
from live_broker.orders.service import (
    LiveBrokerOrderService,
    client_oid_for_internal_order,
)
from live_broker.exceptions import ShadowDivergenceError
from live_broker.private_rest import BitgetPrivateRestClient, BitgetRestError


class InMemoryOrderRepo:
    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.actions: list[dict] = []
        self.kill_switch_events: list[dict] = []
        self.audit_trails: list[dict] = []
        self.fills: list[dict] = []
        self.exchange_snapshots: list[dict] = []
        self._safety_latch_active = False
        self.executions: dict[str, dict] = {}
        self.releases: set[str] = set()
        self.journal: list[dict] = []

    def get_execution_decision(self, execution_id: str):
        return self.executions.get(str(execution_id))

    def get_operator_release(self, execution_id: str):
        if str(execution_id) in self.releases:
            return {"execution_id": str(execution_id)}
        return None

    def record_operator_release(self, **kwargs: object) -> dict:
        eid = str(kwargs.get("execution_id", ""))
        self.releases.add(eid)
        return {"execution_id": eid}

    def record_execution_journal(self, record: dict) -> dict:
        row = {"journal_id": str(uuid4()), **dict(record)}
        self.journal.append(row)
        return row

    def seed_execution_candidate(self, execution_id: UUID, *, symbol: str = "BTCUSDT") -> None:
        self.executions[str(execution_id)] = {
            "execution_id": str(execution_id),
            "decision_action": "live_candidate_recorded",
            "symbol": symbol,
        }

    def seed_operator_release(self, execution_id: UUID) -> None:
        self.releases.add(str(execution_id))

    def latest_reconcile_snapshot(self) -> None:
        return None

    def safety_latch_is_active(self) -> bool:
        return bool(self._safety_latch_active)

    def get_order_by_internal_id(self, internal_order_id: str):
        return self.orders.get(str(internal_order_id))

    def get_order_by_client_oid(self, client_oid: str):
        for order in self.orders.values():
            if order.get("client_oid") == client_oid:
                return order
        return None

    def get_order_by_exchange_order_id(self, exchange_order_id: str):
        for order in self.orders.values():
            if order.get("exchange_order_id") == exchange_order_id:
                return order
        return None

    def upsert_order(self, record: dict):
        stored = dict(record)
        stored.setdefault("created_ts", datetime.now(UTC))
        stored.setdefault("updated_ts", datetime.now(UTC))
        self.orders[str(stored["internal_order_id"])] = stored
        return stored

    def record_order_action(self, record: dict):
        stored = dict(record)
        self.actions.append(stored)
        return stored

    def list_recent_orders(self, limit: int):
        return list(self.orders.values())[:limit]

    def list_active_orders(
        self,
        *,
        limit: int = 200,
        symbol: str | None = None,
        product_type: str | None = None,
        internal_order_id: str | None = None,
    ):
        items = list(self.orders.values())[:limit]
        out = []
        for item in items:
            if item.get("status") in {
                "canceled",
                "filled",
                "error",
                "replaced",
                "flattened",
                "flatten_failed",
                "timed_out",
            }:
                continue
            if symbol and item.get("symbol") != symbol:
                continue
            if product_type and item.get("product_type") != product_type:
                continue
            if internal_order_id and str(item.get("internal_order_id")) != str(internal_order_id):
                continue
            out.append(item)
        return out

    def list_recent_order_actions(self, limit: int):
        return self.actions[:limit]

    def order_status_counts(self):
        counts: dict[str, int] = {}
        for order in self.orders.values():
            status = str(order.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
        return counts

    def record_kill_switch_event(self, record: dict):
        stored = dict(record)
        stored.setdefault("kill_switch_event_id", str(uuid4()))
        stored.setdefault("created_ts", datetime.now(UTC))
        self.kill_switch_events.append(stored)
        return stored

    def list_recent_kill_switch_events(self, limit: int, *, active_only: bool = False):
        if active_only:
            return self.active_kill_switches()[:limit]
        return list(reversed(self.kill_switch_events))[:limit]

    def active_kill_switches(self):
        latest: dict[tuple[str, str], dict] = {}
        for item in self.kill_switch_events:
            if item.get("event_type") not in {"arm", "release"}:
                continue
            latest[(item["scope"], item["scope_key"])] = item
        items = [item for item in latest.values() if item.get("is_active")]
        return sorted(
            items,
            key=lambda row: row.get("created_ts") or datetime.min,
            reverse=True,
        )

    def record_audit_trail(self, record: dict):
        stored = dict(record)
        stored.setdefault("audit_trail_id", str(uuid4()))
        stored.setdefault("created_ts", datetime.now(UTC))
        self.audit_trails.append(stored)
        return stored

    def list_recent_audit_trails(self, limit: int, *, category: str | None = None):
        items = list(reversed(self.audit_trails))
        if category:
            items = [item for item in items if item.get("category") == category]
        return items[:limit]

    def record_fill(self, record: dict):
        stored = dict(record)
        stored.setdefault("created_ts", datetime.now(UTC))
        self.fills.append(stored)
        return stored

    def list_recent_fills(
        self,
        limit: int,
        *,
        symbol: str | None = None,
        internal_order_id: str | None = None,
    ):
        items = list(self.fills)
        if symbol:
            items = [item for item in items if item.get("symbol") == symbol]
        if internal_order_id:
            items = [
                item
                for item in items
                if str(item.get("internal_order_id") or "") == str(internal_order_id)
            ]
        return list(reversed(items))[:limit]

    def record_exchange_snapshot(self, record: dict):
        stored = dict(record)
        stored.setdefault("snapshot_id", str(uuid4()))
        stored.setdefault("created_ts", datetime.now(UTC))
        self.exchange_snapshots.append(stored)
        return stored

    def list_latest_exchange_snapshots(
        self,
        snapshot_type: str,
        *,
        symbol: str | None = None,
        limit: int = 200,
    ):
        latest: dict[tuple[str, str], dict] = {}
        for item in self.exchange_snapshots:
            if item.get("snapshot_type") != snapshot_type:
                continue
            item_symbol = str(item.get("symbol") or "")
            if symbol is not None and item_symbol != symbol:
                continue
            latest[(snapshot_type, item_symbol)] = item
        return list(reversed(list(latest.values())))[:limit]


def test_order_service_blocks_open_when_execution_binding_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_REQUIRE_EXECUTION_BINDING="true")
    repo = InMemoryOrderRepo()
    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(
            settings,
            transport=httpx.MockTransport(
                lambda r: _server_time_response() if r.url.path == "/api/v2/public/time" else httpx.Response(500)
            ),
        ),
    )
    with pytest.raises(BitgetRestError) as exc:
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
    assert exc.value.classification == "validation"
    assert "source_execution_decision_id" in str(exc.value).lower()


def test_order_service_blocks_open_without_operator_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        LIVE_REQUIRE_EXECUTION_BINDING="true",
        LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN="true",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="false",
    )
    repo = InMemoryOrderRepo()
    execution_id = uuid4()
    repo.seed_execution_candidate(execution_id)
    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(
            settings,
            transport=httpx.MockTransport(
                lambda r: _server_time_response()
                if r.url.path == "/api/v2/public/time"
                else httpx.Response(500)
            ),
        ),
    )
    with pytest.raises(BitgetRestError) as exc:
        service.create_order(
            OrderCreateRequest(
                source_service="manual",
                symbol="BTCUSDT",
                side="buy",
                order_type="limit",
                size="0.01",
                price="65000",
                source_execution_decision_id=execution_id,
            )
        )
    assert exc.value.classification == "validation"
    assert "operator_release_required" in str(exc.value)


def test_order_service_blocks_open_without_shadow_match_latch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        LIVE_REQUIRE_EXECUTION_BINDING="true",
        LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN="true",
        REQUIRE_SHADOW_MATCH_BEFORE_LIVE="true",
    )
    repo = InMemoryOrderRepo()
    execution_id = uuid4()
    repo.seed_execution_candidate(execution_id)
    repo.seed_operator_release(execution_id)
    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(
            settings,
            transport=httpx.MockTransport(
                lambda r: _server_time_response()
                if r.url.path == "/api/v2/public/time"
                else httpx.Response(500)
            ),
        ),
    )
    with patch(
        "live_broker.orders.service.get_shadow_match_latch_read_status",
        return_value="absent",
    ):
        with pytest.raises(ShadowDivergenceError) as exc:
            service.create_order(
                OrderCreateRequest(
                    source_service="manual",
                    symbol="BTCUSDT",
                    side="buy",
                    order_type="limit",
                    size="0.01",
                    price="65000",
                    source_execution_decision_id=execution_id,
                )
            )
    assert "shadow_match_latch_absent" in (exc.value.reason or "")


def test_order_service_open_hits_spot_endpoint_when_request_family_spot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/spot/trade/place-order":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "spot-1"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    service.create_order(
        OrderCreateRequest(
            source_service="manual",
            symbol="BTCUSDT",
            market_family="spot",
            side="buy",
            order_type="limit",
            size="0.001",
            price="50000",
        )
    )
    assert "/api/v2/spot/trade/place-order" in seen_paths


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "STRATEGY_EXEC_MODE": "manual",
        "LIVE_BROKER_ENABLED": "true",
        "SHADOW_TRADE_ENABLE": "false",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_REQUIRE_EXECUTION_BINDING": "false",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "false",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "false",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "LIVE_BROKER_BASE_URL": "https://api.bitget.com",
        "LIVE_BROKER_WS_PRIVATE_URL": "wss://ws.bitget.com/v2/ws/private",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_REST_LOCALE": "en-US",
        "ORDER_IDEMPOTENCY_PREFIX": "bgai-test",
        "LIVE_BROKER_HTTP_TIMEOUT_SEC": "5",
        "LIVE_BROKER_HTTP_MAX_RETRIES": "1",
        "LIVE_BROKER_HTTP_RETRY_BASE_SEC": "0.01",
        "LIVE_BROKER_HTTP_RETRY_MAX_SEC": "0.02",
        "LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD": "2",
        "LIVE_BROKER_CIRCUIT_OPEN_SEC": "30",
        "LIVE_BROKER_SERVER_TIME_SYNC_SEC": "5",
        "LIVE_BROKER_SERVER_TIME_MAX_SKEW_MS": "5000",
        "LIVE_ORDER_TIMEOUT_SEC": "60",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def _seed_exchange_long_for_reduce_only_guard(
    repo: InMemoryOrderRepo, *, symbol: str = "BTCUSDT", size: str = "0.01"
) -> None:
    """
    Modelliert Exchange-Positions-Truth fuer LIVE_REQUIRE_EXCHANGE_POSITION_FOR_REDUCE_ONLY
    (sonst blockt der deterministische Reduce-only-Guard ohne Snapshot).
    """
    repo.record_exchange_snapshot(
        {
            "snapshot_type": "positions",
            "symbol": symbol,
            "raw_data": {
                "items": [
                    {"instId": symbol, "total": size, "holdSide": "long"},
                ]
            },
        }
    )


def _server_time_response(server_time: int | None = None) -> httpx.Response:
    """CI-tauglich: ohne festes Epoch (sonst Clock-Skew-Gate ab 2025+)."""
    ts = int(time.time() * 1000) if server_time is None else int(server_time)
    return httpx.Response(
        200,
        json={
            "code": "00000",
            "msg": "success",
            "requestTime": ts,
            "data": {"serverTime": str(ts)},
        },
    )


def test_private_client_retries_rate_limit_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    sleeps: list[float] = []
    order_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            order_calls["count"] += 1
            if order_calls["count"] == 1:
                return httpx.Response(429, json={"code": "429", "msg": "Too many requests"})
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": "bgai-test-crt-abc", "orderId": "12345"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = BitgetPrivateRestClient(
        settings,
        transport=httpx.MockTransport(handler),
        sleep_fn=lambda delay: sleeps.append(float(delay)),
    )
    response = client.place_order(
        {
            "symbol": "BTCUSDT",
            "productType": "USDT-FUTURES",
            "marginMode": "isolated",
            "marginCoin": "USDT",
            "size": "0.01",
            "side": "buy",
            "orderType": "limit",
            "price": "65000",
            "force": "gtc",
            "clientOid": "bgai-test-crt-abc",
            "reduceOnly": "NO",
        }
    )
    assert response.attempts == 2
    assert order_calls["count"] == 2
    assert len(sleeps) == 1


def test_private_client_maps_signature_error_to_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_BROKER_HTTP_MAX_RETRIES="0")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            return httpx.Response(
                200,
                json={
                    "code": "40009",
                    "msg": "sign signature error",
                    "requestTime": int(time.time() * 1000),
                    "data": {},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = BitgetPrivateRestClient(
        settings,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(BitgetRestError) as exc_info:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "65000",
                "force": "gtc",
                "clientOid": "bgai-test-crt-abc",
                "reduceOnly": "NO",
            }
        )
    assert exc_info.value.classification == "auth"
    assert exc_info.value.retryable is False


def test_private_client_opens_circuit_after_retryable_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        LIVE_BROKER_HTTP_MAX_RETRIES="0",
        LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD="1",
    )
    order_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            order_calls["count"] += 1
            return httpx.Response(429, json={"code": "429", "msg": "Too many requests"})
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = BitgetPrivateRestClient(
        settings,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(BitgetRestError) as first_exc:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "65000",
                "force": "gtc",
                "clientOid": "bgai-test-crt-abc",
                "reduceOnly": "NO",
            }
        )
    assert first_exc.value.classification == "rate_limit"
    with pytest.raises(BitgetRestError) as second_exc:
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "65000",
                "force": "gtc",
                "clientOid": "bgai-test-crt-def",
                "reduceOnly": "NO",
            }
        )
    assert second_exc.value.classification == "circuit_open"
    assert order_calls["count"] == 1


def test_order_service_recovers_duplicate_create_via_client_oid_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_BROKER_HTTP_MAX_RETRIES="0")
    repo = InMemoryOrderRepo()
    internal_order_id = UUID("11111111-1111-1111-1111-111111111111")
    expected_client_oid = client_oid_for_internal_order(
        settings.order_idempotency_prefix,
        action_tag="crt",
        internal_order_id=internal_order_id,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            return httpx.Response(
                200,
                json={
                    "code": "01003",
                    "msg": "Duplicate data exists",
                    "requestTime": int(time.time() * 1000),
                    "data": {},
                },
            )
        if request.url.path == "/api/v2/mix/order/detail":
            assert request.url.params["clientOid"] == expected_client_oid
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {
                        "orderId": "778899",
                        "clientOid": expected_client_oid,
                        "symbol": "BTCUSDT",
                        "price": "65000",
                        "size": "0.01",
                        "state": "live",
                        "side": "buy",
                        "marginCoin": "USDT",
                        "marginMode": "isolated",
                        "orderType": "limit",
                        "reduceOnly": "NO",
                    },
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    result = service.create_order(
        OrderCreateRequest(
            internal_order_id=internal_order_id,
            source_service="manual",
            symbol="BTCUSDT",
            side="buy",
            order_type="limit",
            size="0.01",
            price="65000",
        )
    )
    assert result["idempotent"] is True
    assert result["item"]["client_oid"] == expected_client_oid
    assert result["item"]["exchange_order_id"] == "778899"


def test_order_service_reuses_existing_internal_order_without_second_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    internal_order_id = uuid4()
    order_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            order_calls["count"] += 1
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "991122"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    request = OrderCreateRequest(
        internal_order_id=internal_order_id,
        source_service="manual",
        symbol="BTCUSDT",
        side="buy",
        order_type="limit",
        size="0.01",
        price="65000",
    )
    first = service.create_order(request)
    second = service.create_order(request)
    assert first["item"]["internal_order_id"] == str(internal_order_id)
    assert second["idempotent"] is True
    assert order_calls["count"] == 1


def test_kill_switch_blocks_normal_orders_but_allows_reduce_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    _seed_exchange_long_for_reduce_only_guard(repo)
    placed: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-all-orders":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"successList": [], "failureList": []},
                },
            )
        if request.url.path == "/api/v2/mix/order/place-order":
            body = json.loads(request.content.decode("utf-8"))
            placed.append(body)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "111"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    service.arm_kill_switch(
        KillSwitchRequest(scope="service", reason="ops_stop", source="operator")
    )
    with pytest.raises(BitgetRestError) as exc_info:
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
    assert exc_info.value.classification == "kill_switch"
    result = service.create_reduce_only_order(
        ReduceOnlyOrderRequest(
            source_service="manual",
            symbol="BTCUSDT",
            side="sell",
            trade_side="close",
            order_type="market",
            size="0.01",
        )
    )
    assert result["ok"] is True
    assert placed[-1]["reduceOnly"] == "YES"


def test_kill_switch_arm_auto_cancels_existing_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    internal_order_id = str(uuid4())
    repo.upsert_order(
        {
            "internal_order_id": internal_order_id,
            "parent_internal_order_id": None,
            "source_service": "manual",
            "symbol": "BTCUSDT",
            "product_type": "USDT-FUTURES",
            "margin_mode": "isolated",
            "margin_coin": "USDT",
            "side": "buy",
            "trade_side": None,
            "order_type": "limit",
            "force": "gtc",
            "reduce_only": False,
            "size": "0.01",
            "price": "65000",
            "note": "",
            "client_oid": "bgai-test-crt-existing",
            "exchange_order_id": "order-1",
            "status": "submitted",
            "last_action": "create",
            "last_http_status": 200,
            "last_exchange_code": "00000",
            "last_exchange_msg": "success",
            "last_response_json": {},
            "trace_json": {},
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-all-orders":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"successList": [{"orderId": "order-1", "clientOid": "bgai-test-crt-existing"}], "failureList": []},
                },
            )
        if request.url.path == "/api/v2/mix/order/cancel-order":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"orderId": "order-1", "clientOid": "bgai-test-crt-existing"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    result = service.arm_kill_switch(
        KillSwitchRequest(
            scope="account",
            reason="risk_alarm",
            source="operator",
            product_type="USDT-FUTURES",
            margin_coin="USDT",
        )
    )
    assert result["auto_cancel"]["local"]["count"] == 1
    assert repo.orders[internal_order_id]["status"] == "canceled"
    assert repo.kill_switch_events[0]["event_type"] == "arm"
    assert repo.kill_switch_events[-1]["event_type"] == "auto_cancel"
    assert repo.audit_trails


def test_emergency_flatten_bypasses_submit_gate_in_live_mode(
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
    assert placed[-1]["orderType"] == "market"
    assert placed[-1]["reduceOnly"] == "YES"
    assert placed[-1]["tradeSide"] == "close"


def test_trade_kill_switch_blocks_replace_across_replace_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    internal_order_id = str(uuid4())
    repo.upsert_order(
        {
            "internal_order_id": internal_order_id,
            "parent_internal_order_id": None,
            "source_service": "manual",
            "symbol": "BTCUSDT",
            "product_type": "USDT-FUTURES",
            "margin_mode": "isolated",
            "margin_coin": "USDT",
            "side": "buy",
            "trade_side": None,
            "order_type": "limit",
            "force": "gtc",
            "reduce_only": False,
            "size": "0.01",
            "price": "65000",
            "note": "",
            "client_oid": "bgai-test-crt-root",
            "exchange_order_id": "replace-order-1",
            "status": "submitted",
            "last_action": "create",
            "last_http_status": 200,
            "last_exchange_code": "00000",
            "last_exchange_msg": "success",
            "last_response_json": {},
            "trace_json": {},
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/modify-order":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["newClientOid"], "orderId": "replace-order-2"},
                },
            )
        if request.url.path == "/api/v2/mix/order/detail":
            client_oid = request.url.params.get("clientOid")
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {
                        "orderId": "replace-order-2",
                        "clientOid": client_oid,
                        "state": "live",
                    },
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    replaced = service.replace_order(
        OrderReplaceRequest(
            internal_order_id=UUID(internal_order_id),
            new_size="0.02",
            new_price="64000",
        )
    )
    replaced_internal_order_id = replaced["item"]["internal_order_id"]
    service.arm_kill_switch(
        KillSwitchRequest(
            scope="trade",
            reason="trade_stop",
            source="operator",
            internal_order_id=UUID(internal_order_id),
        )
    )
    with pytest.raises(BitgetRestError) as exc_info:
        service.replace_order(
            OrderReplaceRequest(
                internal_order_id=UUID(str(replaced_internal_order_id)),
                new_size="0.03",
                new_price="63000",
            )
        )
    assert exc_info.value.classification == "kill_switch"
    assert repo.active_kill_switches()[0]["scope_key"] == f"order:{internal_order_id}"


def test_cancel_and_query_support_exchange_only_order_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-order":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"orderId": "remote-order-1", "clientOid": "remote-client-1"},
                },
            )
        if request.url.path == "/api/v2/mix/order/detail":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {
                        "orderId": "remote-order-1",
                        "clientOid": "remote-client-1",
                        "state": "canceled",
                        "marginMode": "isolated",
                        "marginCoin": "USDT",
                        "side": "sell",
                        "orderType": "market",
                        "size": "0.02",
                        "reduceOnly": "YES",
                    },
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    cancelled = service.cancel_order(
        OrderCancelRequest(
            order_id="remote-order-1",
            symbol="BTCUSDT",
            product_type="USDT-FUTURES",
            margin_coin="USDT",
        )
    )
    assert cancelled["item"]["exchange_order_id"] == "remote-order-1"
    queried = service.query_order(
        OrderQueryRequest(
            order_id="remote-order-1",
            symbol="BTCUSDT",
            product_type="USDT-FUTURES",
        )
    )
    assert queried["item"]["exchange_order_id"] == "remote-order-1"
    assert queried["item"]["status"] == "canceled"
    assert queried["item"]["reduce_only"] is True


def test_emergency_flatten_resolves_position_from_exchange_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_TRADE_ENABLE="false")
    repo = InMemoryOrderRepo()
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": str(uuid4()),
            "symbol": "BTCUSDT",
            "snapshot_type": "positions",
            "raw_data": {
                "items": [
                    {
                        "instId": "BTCUSDT",
                        "holdSide": "long",
                        "total": "0.03",
                    }
                ]
            },
        }
    )
    placed: list[dict] = []
    cancel_all_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-all-orders":
            cancel_all_calls["count"] += 1
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"successList": [], "failureList": []},
                },
            )
        if request.url.path == "/api/v2/mix/order/place-order":
            body = json.loads(request.content.decode("utf-8"))
            placed.append(body)
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "flatten-3"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    result = service.emergency_flatten(
        EmergencyFlattenRequest(
            source_service="manual",
            symbol="BTCUSDT",
            reason="panic_auto",
        )
    )
    assert result["flattened"] is True
    assert result["resolved_order"]["resolved_from"] == "exchange_positions"
    assert cancel_all_calls["count"] == 1
    assert placed[-1]["side"] == "sell"
    assert placed[-1]["size"] == "0.03"
    assert placed[-1]["reduceOnly"] == "YES"


def test_release_kill_switch_preserves_active_state_through_flatten_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_TRADE_ENABLE="false")
    repo = InMemoryOrderRepo()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-all-orders":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"successList": [], "failureList": []},
                },
            )
        if request.url.path == "/api/v2/mix/order/place-order":
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "flatten-4"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    service.arm_kill_switch(
        KillSwitchRequest(scope="service", reason="ops_stop", source="operator")
    )
    assert repo.active_kill_switches()[0]["event_type"] == "arm"
    service.emergency_flatten(
        EmergencyFlattenRequest(
            source_service="manual",
            symbol="BTCUSDT",
            side="sell",
            size="0.01",
            reason="panic_button",
        )
    )
    active = repo.active_kill_switches()
    assert len(active) == 1
    assert active[0]["event_type"] == "arm"
    released = service.release_kill_switch(
        KillSwitchRequest(scope="service", reason="resume", source="operator")
    )
    assert released["item"]["event_type"] == "release"
    assert repo.active_kill_switches() == []


def test_emergency_flatten_bypasses_open_circuit_with_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        LIVE_BROKER_HTTP_MAX_RETRIES="0",
        LIVE_BROKER_CIRCUIT_FAIL_THRESHOLD="1",
    )
    repo = InMemoryOrderRepo()
    _seed_exchange_long_for_reduce_only_guard(repo)
    order_calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/place-order":
            order_calls["count"] += 1
            if order_calls["count"] == 1:
                return httpx.Response(429, json={"code": "429", "msg": "Too many requests"})
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"clientOid": body["clientOid"], "orderId": "flatten-2"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    client = BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler))
    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        client,
    )
    with pytest.raises(BitgetRestError):
        client.place_order(
            {
                "symbol": "BTCUSDT",
                "productType": "USDT-FUTURES",
                "marginMode": "isolated",
                "marginCoin": "USDT",
                "size": "0.01",
                "side": "buy",
                "orderType": "limit",
                "price": "65000",
                "force": "gtc",
                "clientOid": "bgai-test-crt-circuit",
                "reduceOnly": "NO",
            }
        )
    result = service.emergency_flatten(
        EmergencyFlattenRequest(
            source_service="manual",
            symbol="BTCUSDT",
            side="sell",
            size="0.01",
            reason="priority_bypass",
        )
    )
    assert result["ok"] is True
    assert order_calls["count"] == 2


def test_order_timeout_cancels_stale_orders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, LIVE_ORDER_TIMEOUT_SEC="30")
    repo = InMemoryOrderRepo()
    internal_order_id = str(uuid4())
    repo.upsert_order(
        {
            "internal_order_id": internal_order_id,
            "parent_internal_order_id": None,
            "source_service": "manual",
            "symbol": "BTCUSDT",
            "product_type": "USDT-FUTURES",
            "margin_mode": "isolated",
            "margin_coin": "USDT",
            "side": "buy",
            "trade_side": None,
            "order_type": "limit",
            "force": "gtc",
            "reduce_only": False,
            "size": "0.01",
            "price": "65000",
            "note": "",
            "client_oid": "bgai-test-crt-timeout",
            "exchange_order_id": "timeout-order",
            "status": "submitted",
            "last_action": "create",
            "last_http_status": 200,
            "last_exchange_code": "00000",
            "last_exchange_msg": "success",
            "last_response_json": {},
            "trace_json": {},
            "created_ts": datetime.now(UTC) - timedelta(seconds=61),
            "updated_ts": datetime.now(UTC) - timedelta(seconds=61),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-order":
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"orderId": "timeout-order", "clientOid": "bgai-test-crt-timeout"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    result = service.run_order_timeouts()
    assert result["timed_out"] == 1
    assert repo.orders[internal_order_id]["status"] == "timed_out"
    assert repo.orders[internal_order_id]["last_action"] == "timeout_cancel"
    assert any(item["category"] == "order_timeout" for item in repo.audit_trails)


def test_safety_latch_blocks_create_order_allows_reduce_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                    "data": {"clientOid": body["clientOid"], "orderId": "latched-ro"},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(BitgetRestError) as exc_info:
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
    assert exc_info.value.classification == "kill_switch"
    ro = service.create_reduce_only_order(
        ReduceOnlyOrderRequest(
            source_service="manual",
            symbol="BTCUSDT",
            side="sell",
            trade_side="close",
            order_type="market",
            size="0.01",
        )
    )
    assert ro["ok"] is True
    assert placed[-1]["reduceOnly"] == "YES"


def test_release_safety_latch_idempotent_when_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    out = service.release_safety_latch(SafetyLatchReleaseRequest(reason="restart_smoke"))
    assert out == {"ok": True, "idempotent": True}


def test_arm_kill_switch_second_call_idempotent_skips_extra_cancel_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()
    cancel_all_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        if request.url.path == "/api/v2/mix/order/cancel-all-orders":
            cancel_all_calls["n"] += 1
            return httpx.Response(
                200,
                json={
                    "code": "00000",
                    "msg": "success",
                    "requestTime": int(time.time() * 1000),
                    "data": {"successList": [], "failureList": []},
                },
            )
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    req = KillSwitchRequest(scope="service", reason="unit_idem", source="operator")
    first = service.arm_kill_switch(req)
    assert first.get("idempotent") is not True
    assert cancel_all_calls["n"] == 1
    second = service.arm_kill_switch(req)
    assert second.get("idempotent") is True
    assert cancel_all_calls["n"] == 1


def test_release_kill_switch_idempotent_when_not_armed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryOrderRepo()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v2/public/time":
            return _server_time_response()
        raise AssertionError(f"unexpected path: {request.url.path}")

    service = LiveBrokerOrderService(
        settings,
        repo,  # type: ignore[arg-type]
        BitgetPrivateRestClient(settings, transport=httpx.MockTransport(handler)),
    )
    out = service.release_kill_switch(
        KillSwitchRequest(scope="service", reason="noop", source="operator")
    )
    assert out == {"ok": True, "idempotent": True, "item": None}
