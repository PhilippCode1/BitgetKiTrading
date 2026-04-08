from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"

for candidate in (REPO_ROOT, LIVE_BROKER_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from live_broker.config import LiveBrokerSettings
from live_broker.private_ws.models import NormalizedPrivateEvent
from live_broker.private_ws.sync import ExchangeStateSyncService
from live_broker.reconcile.service import LiveReconcileService


class InMemoryJournalRepo:
    def __init__(self) -> None:
        self.orders: dict[str, dict] = {}
        self.fills: dict[str, dict] = {}
        self.exchange_snapshots: list[dict] = []
        self.reconcile_snapshots: list[dict] = []
        self.reconcile_runs: list[dict] = []
        self.audit_trails: list[dict] = []
        self.execution_journal: list[dict] = []
        self.exit_plans: list[dict] = []

    def schema_ready(self):
        return True, "ok"

    def decision_action_counts(self):
        return {}

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
        key = str(record["internal_order_id"])
        existing = self.orders.get(key, {})
        stored = {**existing, **record}
        stored.setdefault("created_ts", existing.get("created_ts") or datetime.now(UTC))
        stored.setdefault("updated_ts", existing.get("updated_ts") or datetime.now(UTC))
        self.orders[key] = stored
        return stored

    def list_active_orders(
        self,
        *,
        limit: int = 200,
        symbol: str | None = None,
        product_type: str | None = None,
        internal_order_id: str | None = None,
    ):
        terminal = {
            "canceled",
            "filled",
            "error",
            "replaced",
            "flattened",
            "flatten_failed",
            "timed_out",
        }
        items = list(self.orders.values())[:limit]
        out = []
        for item in items:
            if str(item.get("status") or "").lower() in terminal:
                continue
            if symbol and item.get("symbol") != symbol:
                continue
            if product_type and item.get("product_type") != product_type:
                continue
            if internal_order_id and str(item.get("internal_order_id")) != str(internal_order_id):
                continue
            out.append(item)
        return out

    def record_fill(self, record: dict):
        key = str(record["exchange_trade_id"])
        stored = {**self.fills.get(key, {}), **record}
        stored.setdefault("created_ts", datetime.now(UTC))
        self.fills[key] = stored
        return stored

    def list_recent_fills(
        self,
        limit: int,
        *,
        symbol: str | None = None,
        internal_order_id: str | None = None,
    ):
        items = list(self.fills.values())
        if symbol:
            items = [item for item in items if item.get("symbol") == symbol]
        if internal_order_id:
            items = [item for item in items if str(item.get("internal_order_id")) == str(internal_order_id)]
        return list(reversed(items))[:limit]

    def record_exchange_snapshot(self, record: dict):
        stored = dict(record)
        stored.setdefault("snapshot_id", str(uuid4()))
        stored.setdefault("created_ts", datetime.now(UTC))
        self.exchange_snapshots.append(stored)
        return stored

    def list_recent_execution_journal(self, limit: int = 200):
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        items = sorted(
            self.execution_journal,
            key=lambda r: r.get("created_ts") or epoch,
            reverse=True,
        )
        return items[: max(1, min(1000, int(limit)))]

    def list_active_exit_plans(
        self,
        *,
        limit: int = 200,
        symbol: str | None = None,
    ):
        active_states = {"pending", "active", "closing"}
        rows = [p for p in self.exit_plans if str(p.get("state") or "") in active_states]
        if symbol is not None:
            rows = [p for p in rows if str(p.get("symbol") or "") == symbol]
        return rows[:limit]

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
            if symbol is not None and item.get("symbol") != symbol:
                continue
            latest[(str(item["snapshot_type"]), str(item["symbol"]))] = item
        return list(latest.values())[:limit]

    def reconstruct_runtime_state(
        self,
        *,
        order_limit: int = 500,
        fill_limit: int = 500,
        journal_limit: int = 200,
        exit_plan_limit: int = 200,
    ):
        open_orders = self.list_active_orders(limit=order_limit)
        order_snapshots = self.list_latest_exchange_snapshots("orders", limit=order_limit)
        position_snapshots = self.list_latest_exchange_snapshots("positions", limit=order_limit)
        account_snapshots = self.list_latest_exchange_snapshots("account", limit=order_limit)
        recent_fills = self.list_recent_fills(fill_limit)
        journal_recent = self.list_recent_execution_journal(journal_limit)
        exit_plans = self.list_active_exit_plans(limit=exit_plan_limit)
        by_state: dict[str, int] = {}
        for plan in exit_plans:
            st = str(plan.get("state") or "unknown")
            by_state[st] = by_state.get(st, 0) + 1
        return {
            "open_orders": open_orders,
            "exchange_order_snapshots": order_snapshots,
            "exchange_position_snapshots": position_snapshots,
            "exchange_account_snapshots": account_snapshots,
            "recent_fills": recent_fills,
            "execution_journal_recent": journal_recent,
            "active_exit_plans": exit_plans,
            "active_exit_plans_summary": {"total": len(exit_plans), "by_state": by_state},
            "open_order_count": len(open_orders),
            "exchange_order_snapshot_count": len(order_snapshots),
            "exchange_position_snapshot_count": len(position_snapshots),
            "exchange_account_snapshot_count": len(account_snapshots),
            "recent_fill_count": len(recent_fills),
            "execution_journal_recent_count": len(journal_recent),
        }

    def begin_reconcile_run(self, trigger_reason: str, meta_json: dict | None = None) -> dict:
        rid = str(uuid4())
        row = {
            "reconcile_run_id": rid,
            "trigger_reason": trigger_reason,
            "meta_json": dict(meta_json or {}),
            "status": "running",
            "started_ts": datetime.now(UTC),
            "completed_ts": None,
        }
        self.reconcile_runs.append(row)
        return row

    def complete_reconcile_run(
        self,
        reconcile_run_id: str,
        status: str,
        meta_patch: dict | None = None,
    ) -> None:
        for item in self.reconcile_runs:
            if str(item.get("reconcile_run_id")) == str(reconcile_run_id):
                item["status"] = status
                item["completed_ts"] = datetime.now(UTC)
                base = dict(item.get("meta_json") or {})
                base.update(meta_patch or {})
                item["meta_json"] = base
                break

    def record_reconcile_snapshot(self, record: dict):
        stored = dict(record)
        stored.setdefault("reconcile_snapshot_id", str(uuid4()))
        stored.setdefault("created_ts", datetime.now(UTC))
        self.reconcile_snapshots.append(stored)
        return stored

    def latest_reconcile_snapshot(self):
        if not self.reconcile_snapshots:
            return None
        return self.reconcile_snapshots[-1]

    def safety_latch_is_active(self) -> bool:
        for row in reversed(self.audit_trails):
            if row.get("category") == "safety_latch":
                return row.get("action") == "arm"
        return False

    def record_audit_trail(self, record: dict):
        row = dict(record)
        self.audit_trails.append(row)
        return row


class FakeExchangeClient:
    def describe(self) -> dict:
        return {
            "effective_rest_base_url": "https://api.bitget.com",
            "effective_ws_private_url": "wss://ws.bitget.com/v2/ws/private",
            "market_family": "futures",
            "product_type": "USDT-FUTURES",
            "margin_coin": "USDT",
            "margin_account_mode": "isolated",
            "locale": "en-US",
            "symbol": "BTCUSDT",
            "demo_mode": False,
            "live_broker_enabled": True,
            "live_allow_order_submit": False,
        }

    def probe_exchange(self, private_rest=None):
        out: dict = {
            **self.describe(),
            "public_api_ok": True,
            "public_detail": "ok",
            "private_api_configured": True,
            "private_detail": "ok",
            "private_detail_de": "ok",
            "private_auth_ok": True,
            "private_auth_detail": "ok",
            "private_auth_detail_de": "ok",
            "private_auth_classification": None,
            "private_auth_exchange_code": None,
            "market_snapshot": {"last_price": "65000"},
        }
        if private_rest is not None:
            out["credential_profile"] = "live"
            out["credential_isolation_relaxed"] = False
            out["paptrading_header_active"] = False
            out["bitget_private_rest"] = private_rest.state_snapshot()
        return out


class FakeExchangeClientPrivateDown(FakeExchangeClient):
    def probe_exchange(self, private_rest=None):
        out: dict = {
            **self.describe(),
            "public_api_ok": True,
            "public_detail": "ok",
            "private_api_configured": False,
            "private_detail": "simulated_private_down",
            "private_detail_de": "simulated_private_down",
            "private_auth_ok": None,
            "private_auth_detail": None,
            "private_auth_detail_de": None,
            "private_auth_classification": None,
            "private_auth_exchange_code": None,
            "market_snapshot": {"last_price": "65000"},
        }
        if private_rest is not None:
            out["credential_profile"] = "live"
            out["credential_isolation_relaxed"] = False
            out["paptrading_header_active"] = False
            out["bitget_private_rest"] = private_rest.state_snapshot()
        return out


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "manual",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_REQUIRE_EXCHANGE_HEALTH": "false",
        "BITGET_SYMBOL": "ETHUSDT",
        "BITGET_MARKET_FAMILY": "futures",
        "BITGET_PRODUCT_TYPE": "USDT-FUTURES",
        "BITGET_MARGIN_COIN": "USDT",
        "BITGET_API_KEY": "key",
        "BITGET_API_SECRET": "secret",
        "BITGET_API_PASSPHRASE": "pass",
        "LIVE_RECONCILE_INTERVAL_SEC": "15",
    }
    values.update(extra)
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return LiveBrokerSettings()


def test_exchange_state_sync_persists_orders_fills_and_snapshots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch)
    repo = InMemoryJournalRepo()
    sync = ExchangeStateSyncService(settings, repo)  # type: ignore[arg-type]

    order_event = NormalizedPrivateEvent.from_ws_message(
        {
            "action": "snapshot",
            "arg": {
                "instType": "USDT-FUTURES",
                "instId": "default",
                "channel": "orders",
            },
            "data": [
                {
                    "orderId": "1001",
                    "clientOid": "bgai-crt-1001",
                    "instId": "BTCUSDT",
                    "marginCoin": "USDT",
                    "marginMode": "isolated",
                    "side": "buy",
                    "tradeSide": "open",
                    "orderType": "limit",
                    "force": "gtc",
                    "reduceOnly": "no",
                    "size": "0.10",
                    "price": "65000",
                    "status": "live",
                }
            ],
            "ts": 1_700_000_000_000,
        }
    )
    fill_event = NormalizedPrivateEvent.from_ws_message(
        {
            "action": "snapshot",
            "arg": {
                "instType": "USDT-FUTURES",
                "instId": "default",
                "channel": "fill",
            },
            "data": [
                {
                    "orderId": "1001",
                    "clientOid": "bgai-crt-1001",
                    "tradeId": "trade-1",
                    "symbol": "BTCUSDT",
                    "side": "buy",
                    "orderType": "limit",
                    "price": "65000",
                    "baseVolume": "0.10",
                    "tradeSide": "open",
                    "tradeScope": "maker",
                    "feeDetail": [{"feeCoin": "USDT", "totalFee": "-0.01"}],
                    "uTime": "1700000000010",
                }
            ],
            "ts": 1_700_000_000_010,
        }
    )
    position_event = NormalizedPrivateEvent.from_ws_message(
        {
            "action": "snapshot",
            "arg": {
                "instType": "USDT-FUTURES",
                "instId": "default",
                "channel": "positions",
            },
            "data": [
                {
                    "instId": "BTCUSDT",
                    "holdSide": "long",
                    "total": "0.10",
                }
            ],
            "ts": 1_700_000_000_020,
        }
    )
    account_event = NormalizedPrivateEvent.from_ws_message(
        {
            "action": "snapshot",
            "arg": {
                "instType": "USDT-FUTURES",
                "coin": "default",
                "channel": "account",
            },
            "data": [
                {
                    "marginCoin": "USDT",
                    "equity": "100.0",
                }
            ],
            "ts": 1_700_000_000_030,
        }
    )

    sync.handle_event(order_event)
    sync.handle_event(fill_event)
    sync.handle_event(position_event)
    sync.handle_event(account_event)

    stored_order = repo.get_order_by_client_oid("bgai-crt-1001")
    assert stored_order is not None
    assert stored_order["exchange_order_id"] == "1001"
    assert stored_order["status"] == "live"
    assert len(repo.fills) == 1
    stored_fill = repo.list_recent_fills(10)[0]
    assert stored_fill["internal_order_id"] == stored_order["internal_order_id"]
    assert stored_fill["exchange_trade_id"] == "trade-1"
    assert len(repo.list_latest_exchange_snapshots("orders")) == 1
    assert len(repo.list_latest_exchange_snapshots("positions")) == 1
    assert len(repo.list_latest_exchange_snapshots("account")) == 1


def test_reconcile_marks_drift_and_returns_restartable_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(monkeypatch, EXECUTION_MODE="live", SHADOW_TRADE_ENABLE="false", LIVE_TRADE_ENABLE="true")
    repo = InMemoryJournalRepo()
    repo.upsert_order(
        {
            "internal_order_id": str(uuid4()),
            "parent_internal_order_id": None,
            "source_service": "manual",
            "symbol": "BTCUSDT",
            "product_type": "USDT-FUTURES",
            "margin_mode": "isolated",
            "margin_coin": "USDT",
            "side": "buy",
            "trade_side": "open",
            "order_type": "limit",
            "force": "gtc",
            "reduce_only": False,
            "size": "0.10",
            "price": "65000",
            "note": "",
            "client_oid": "bgai-local-only",
            "exchange_order_id": "local-only-order",
            "status": "submitted",
            "last_action": "create",
            "last_http_status": 200,
            "last_exchange_code": "00000",
            "last_exchange_msg": "success",
            "last_response_json": {},
            "trace_json": {},
            "created_ts": datetime.now(UTC) - timedelta(seconds=120),
            "updated_ts": datetime.now(UTC) - timedelta(seconds=120),
        }
    )
    repo.record_fill(
        {
            "internal_order_id": str(uuid4()),
            "exchange_order_id": "filled-order",
            "exchange_trade_id": "fill-1",
            "symbol": "BTCUSDT",
            "side": "buy",
            "price": "65000",
            "size": "0.50",
            "fee": "-0.01",
            "fee_coin": "USDT",
            "is_maker": False,
            "exchange_ts_ms": "1700000000000",
            "raw_json": {"tradeSide": "open"},
        }
    )
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "BTCUSDT",
            "snapshot_type": "orders",
            "raw_data": {
                "items": [
                    {
                        "orderId": "exchange-only-order",
                        "clientOid": "bgai-exchange-only",
                        "instId": "BTCUSDT",
                        "status": "live",
                    }
                ]
            },
        }
    )
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "BTCUSDT",
            "snapshot_type": "positions",
            "raw_data": {
                "items": [
                    {
                        "instId": "BTCUSDT",
                        "holdSide": "long",
                        "total": "1.00",
                    }
                ]
            },
        }
    )
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "USDT",
            "snapshot_type": "account",
            "raw_data": {"items": [{"marginCoin": "USDT", "equity": "100.0"}]},
        }
    )

    service = LiveReconcileService(
        settings,
        FakeExchangeClient(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        bus=None,
    )
    recovery_state = service.restore_runtime_state()
    assert recovery_state["open_order_count"] == 1
    assert recovery_state["exchange_position_snapshot_count"] == 1

    result = service.run_once(reason="unit_test")
    drift = result["details_json"]["drift"]

    assert result["status"] == "degraded"
    assert drift["order"]["local_only_count"] == 1
    assert drift["order"]["exchange_only_count"] == 1
    assert drift["positions"]["mismatch_count"] == 1
    assert repo.latest_reconcile_snapshot() is not None


def test_reconcile_fail_live_arms_safety_latch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
    )
    repo = InMemoryJournalRepo()
    service = LiveReconcileService(
        settings,
        FakeExchangeClientPrivateDown(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        bus=None,
    )
    result = service.run_once(reason="unit_latch_test")
    assert result["status"] == "fail"
    assert repo.safety_latch_is_active() is True
    assert any(
        a.get("category") == "safety_latch" and a.get("action") == "arm" for a in repo.audit_trails
    )


def test_reconcile_empty_journal_live_mode_degraded_missing_snapshots_no_latch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restart ohne Exchange-Snapshots: Drift durch fehlende Truth-Layer, kein Safety-Latch (nur bei fail)."""
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
    )
    repo = InMemoryJournalRepo()
    service = LiveReconcileService(
        settings,
        FakeExchangeClient(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        bus=None,
    )
    recovery = service.restore_runtime_state()
    assert recovery["open_order_count"] == 0
    assert recovery["exchange_position_snapshot_count"] == 0
    result = service.run_once(reason="cold_start_empty")
    assert result["status"] == "degraded"
    drift = result["details_json"]["drift"]
    assert int(drift["snapshot_health"]["missing_count"]) >= 1
    assert repo.safety_latch_is_active() is False


def test_reconcile_skips_exchange_expectations_in_paper_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="paper",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="false",
        LIVE_BROKER_ENABLED="false",
    )
    repo = InMemoryJournalRepo()
    service = LiveReconcileService(
        settings,
        FakeExchangeClient(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        bus=None,
    )

    result = service.run_once(reason="paper_mode")
    drift = result["details_json"]["drift"]

    assert result["status"] == "ok"
    assert drift["total_count"] == 0
    assert drift["snapshot_health"]["exchange_state_expected"] is False
    assert drift["divergence"]["applicable"] is False


def test_reconcile_divergence_missing_exchange_ack_and_journal_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
    )
    repo = InMemoryJournalRepo()
    oid = str(uuid4())
    repo.upsert_order(
        {
            "internal_order_id": oid,
            "parent_internal_order_id": None,
            "source_service": "manual",
            "symbol": "BTCUSDT",
            "product_type": "USDT-FUTURES",
            "margin_mode": "isolated",
            "margin_coin": "USDT",
            "side": "buy",
            "trade_side": "open",
            "order_type": "limit",
            "force": "gtc",
            "reduce_only": False,
            "size": "0.10",
            "price": "65000",
            "note": "",
            "client_oid": "bgai-no-ack",
            "exchange_order_id": None,
            "status": "submitted",
            "last_action": "create",
            "last_http_status": 200,
            "last_exchange_code": "00000",
            "last_exchange_msg": "success",
            "last_response_json": {},
            "trace_json": {},
            "created_ts": datetime.now(UTC) - timedelta(seconds=400),
            "updated_ts": datetime.now(UTC) - timedelta(seconds=400),
        }
    )
    repo.execution_journal.append(
        {
            "journal_id": str(uuid4()),
            "internal_order_id": oid,
            "phase": "order_submit",
            "execution_decision_id": None,
            "created_ts": datetime.now(UTC),
        }
    )
    now = datetime.now(UTC)
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "BTCUSDT",
            "snapshot_type": "orders",
            "raw_data": {"items": []},
            "created_ts": now,
        }
    )
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "BTCUSDT",
            "snapshot_type": "positions",
            "raw_data": {"items": []},
            "created_ts": now,
        }
    )
    repo.record_exchange_snapshot(
        {
            "reconcile_run_id": None,
            "symbol": "USDT",
            "snapshot_type": "account",
            "raw_data": {"items": [{"marginCoin": "USDT", "equity": "1"}]},
            "created_ts": now,
        }
    )
    service = LiveReconcileService(
        settings,
        FakeExchangeClient(),  # type: ignore[arg-type]
        repo,  # type: ignore[arg-type]
        bus=None,
    )
    ws_telemetry = {
        "private_ws": {
            "connection_state": "connected",
            "last_event_ts_ms": int(time.time() * 1000),
            "received_events": 10,
            "reconnect_count": 0,
        }
    }
    result = service.run_once(reason="divergence_unit", worker_telemetry=ws_telemetry)
    drift = result["details_json"]["drift"]
    div = drift["divergence"]
    assert div["missing_exchange_ack"]["count"] == 1
    assert div["journal_tail"]["open_orders_latest_phase_submit_count"] == 1
    assert div["degrade_increment_from_divergence"] >= 1
    assert drift["total_count"] >= int(div["degrade_increment_from_divergence"])
