from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from live_broker.config import LiveBrokerSettings
from live_broker.exits.service import LiveExitService
from live_broker.orders.models import OrderCreateRequest
from live_broker.private_rest import BitgetRestError


class _FakeRepo:
    def __init__(self) -> None:
        self.exit_plans: dict[str, dict] = {}
        self.audit_trails: list[dict] = []
        self.exchange_snapshots: list[dict] = []

    def upsert_exit_plan(self, record: dict) -> dict:
        stored = dict(record)
        stored.setdefault("plan_id", str(uuid4()))
        self.exit_plans[str(stored["root_internal_order_id"])] = stored
        return stored

    def get_exit_plan_by_root_order(self, root_internal_order_id: str) -> dict | None:
        return self.exit_plans.get(str(root_internal_order_id))

    def list_active_exit_plans(self, *, limit: int = 200, symbol: str | None = None) -> list[dict]:
        items = [
            value
            for value in self.exit_plans.values()
            if value.get("state") in {"pending", "active", "closing"}
        ]
        if symbol is not None:
            items = [item for item in items if item.get("symbol") == symbol]
        return items[:limit]

    def record_audit_trail(self, record: dict) -> dict:
        stored = dict(record)
        self.audit_trails.append(stored)
        return stored

    def list_latest_exchange_snapshots(
        self,
        snapshot_type: str,
        *,
        symbol: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        items = [item for item in self.exchange_snapshots if item.get("snapshot_type") == snapshot_type]
        if symbol is not None:
            items = [item for item in items if item.get("symbol") == symbol]
        return items[:limit]


class _FakeOrderService:
    def __init__(self) -> None:
        self.submitted: list[dict] = []

    def trade_root_internal_order_id(self, internal_order_id: str) -> str:
        return str(internal_order_id)

    def create_reduce_only_order(self, request, *, priority: bool, allow_safety_bypass: bool) -> dict:
        self.submitted.append(
            {
                **request.model_dump(),
                "priority": priority,
                "allow_safety_bypass": allow_safety_bypass,
            }
        )
        return {"ok": True, "item": request.model_dump()}


class _FakeExchangeClient:
    def __init__(self) -> None:
        self.snapshot = {
            "symbol": "BTCUSDT",
            "mark_price": "100",
            "bid_price": "100",
            "ask_price": "100.2",
            "last_price": "100",
        }

    def get_market_snapshot(self, symbol: str) -> dict:
        return {**self.snapshot, "symbol": symbol}


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
        "LIVE_ALLOWED_SYMBOLS": "BTCUSDT,ETHUSDT",
        "LIVE_ALLOWED_MARKET_FAMILIES": "futures,spot,margin",
        "LIVE_ALLOWED_PRODUCT_TYPES": "USDT-FUTURES",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def test_preview_order_exit_plan_blocks_leverage_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = LiveExitService(
        _settings(monkeypatch),
        _FakeRepo(),  # type: ignore[arg-type]
        _FakeExchangeClient(),  # type: ignore[arg-type]
        _FakeOrderService(),  # type: ignore[arg-type]
    )

    with pytest.raises(BitgetRestError) as exc:
        service.preview_order_exit_plan(
            internal_order_id=str(uuid4()),
            request=OrderCreateRequest(
                source_service="manual",
                    symbol="BTCUSDT",
                side="buy",
                trade_side="open",
                order_type="limit",
                size="0.01",
                price="100",
                preset_stop_loss_price="99.8",
                preset_stop_surplus_price="109",
                trace={"leverage": 15, "allowed_leverage": 7},
            ),
        )

    assert "exit_plan_exceeds_allowed_leverage" in str(exc.value)


def test_run_once_submits_reduce_only_partials_and_updates_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepo()
    order_service = _FakeOrderService()
    exchange = _FakeExchangeClient()
    service = LiveExitService(
        _settings(monkeypatch),
        repo,  # type: ignore[arg-type]
        exchange,  # type: ignore[arg-type]
        order_service,  # type: ignore[arg-type]
    )
    root_order_id = str(uuid4())
    preview = service.preview_order_exit_plan(
        internal_order_id=root_order_id,
        request=OrderCreateRequest(
            source_service="manual",
                symbol="BTCUSDT",
            side="buy",
            trade_side="open",
            order_type="limit",
            size="1",
            price="100",
                preset_stop_loss_price="99.8",
                preset_stop_surplus_price="103",
            trace={"leverage": 7, "allowed_leverage": 7, "signal_id": "sig-1", "timeframe": "5m"},
        ),
    )
    assert preview is not None
    service.persist_order_exit_plan(order={"internal_order_id": root_order_id}, preview=preview)
    repo.exchange_snapshots.append(
        {
            "snapshot_type": "positions",
            "symbol": "BTCUSDT",
            "raw_data": {
                "items": [
                    {"instId": "BTCUSDT", "holdSide": "long", "total": "1", "openPriceAvg": "100"}
                ]
            },
        }
    )
    exchange.snapshot = {
        "symbol": "BTCUSDT",
        "mark_price": "101.7",
        "bid_price": "101.7",
        "ask_price": "101.9",
        "last_price": "101.7",
    }

    summary = service.run_once(reason="test")
    plan = repo.get_exit_plan_by_root_order(root_order_id)

    assert summary["exit_orders_submitted"] == 2
    assert len(order_service.submitted) == 2
    assert plan is not None
    assert plan["state"] == "active"
    assert plan["remaining_qty"] == "0.40000000"
    assert plan["tp_plan_json"]["execution_state"]["hit_tp_indices"] == [0, 1]
    assert plan["tp_plan_json"]["break_even"]["applied"] is True
    assert plan["tp_plan_json"]["runner"]["armed"] is True
    assert {item["trace"]["reason"] for item in order_service.submitted} == {"take_profit_hit"}


def test_run_once_submits_runner_trail_close_and_marks_plan_closing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepo()
    order_service = _FakeOrderService()
    exchange = _FakeExchangeClient()
    service = LiveExitService(
        _settings(monkeypatch),
        repo,  # type: ignore[arg-type]
        exchange,  # type: ignore[arg-type]
        order_service,  # type: ignore[arg-type]
    )
    root_order_id = str(uuid4())
    preview = service.preview_order_exit_plan(
        internal_order_id=root_order_id,
        request=OrderCreateRequest(
            source_service="manual",
                symbol="BTCUSDT",
            side="buy",
            trade_side="open",
            order_type="limit",
            size="1",
            price="100",
                preset_stop_loss_price="99.8",
                preset_stop_surplus_price="103",
            trace={"leverage": 7, "allowed_leverage": 7},
        ),
    )
    assert preview is not None
    preview["remaining_qty"] = "0.4"
    preview["tp_plan_json"]["execution_state"]["hit_tp_indices"] = [0, 1]
    preview["tp_plan_json"]["break_even"]["applied"] = True
    preview["tp_plan_json"]["runner"]["armed"] = True
    preview["tp_plan_json"]["runner"]["high_water"] = "101.7"
    preview["tp_plan_json"]["runner"]["trail_stop"] = "100.7"
    repo.upsert_exit_plan(preview)
    repo.exchange_snapshots.append(
        {
            "snapshot_type": "positions",
            "symbol": "BTCUSDT",
            "raw_data": {
                "items": [
                    {"instId": "BTCUSDT", "holdSide": "long", "total": "0.4", "openPriceAvg": "100"}
                ]
            },
        }
    )
    exchange.snapshot = {
        "symbol": "BTCUSDT",
        "mark_price": "100.6",
        "bid_price": "100.6",
        "ask_price": "100.8",
        "last_price": "100.6",
    }

    summary = service.run_once(reason="test_runner")
    plan = repo.get_exit_plan_by_root_order(root_order_id)

    assert summary["exit_orders_submitted"] == 1
    assert len(order_service.submitted) == 1
    assert order_service.submitted[0]["trace"]["reason"] == "runner_trail_hit"
    assert plan is not None
    assert plan["state"] == "closing"
