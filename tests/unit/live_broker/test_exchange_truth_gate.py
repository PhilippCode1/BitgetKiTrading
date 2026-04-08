"""Exchange-Truth-Gate: Live-Submit nur bei konsistentem Reconcile und frischem WS/REST-Catchup."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.service import LiveExecutionService


class _FakeExchangeClient:
    def build_order_preview(self, intent):
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self):
        return {"exchange": "bitget"}

    def private_api_configured(self):
        return True, "ok"


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshots: dict[str, list] = {"account": [], "positions": [], "orders": []}
        self.reconcile_snapshot: dict | None = None

    def record_execution_decision(self, record: dict):
        return {**record, "execution_id": str(uuid4())}

    def record_execution_risk_snapshot(self, execution_decision_id: str, risk_decision: dict) -> None:
        return None

    def record_shadow_live_assessment(self, **kwargs) -> None:
        return None

    def list_latest_exchange_snapshots(self, snapshot_type: str, *, symbol=None, limit: int = 200):
        items = list(self.snapshots.get(snapshot_type, []))
        if symbol is not None:
            items = [i for i in items if i.get("symbol") == symbol]
        return items[:limit]

    def list_exchange_snapshots_since(self, snapshot_type: str, *, since_ts_ms: int, limit: int = 5000):
        return self.list_latest_exchange_snapshots(snapshot_type, limit=limit)

    def latest_reconcile_snapshot(self):
        return self.reconcile_snapshot

    def fetch_online_drift_state(self):
        return None


def _live_settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "live",
        "STRATEGY_EXEC_MODE": "auto",
        "SHADOW_TRADE_ENABLE": "false",
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
        "RISK_MAX_POSITION_RISK_PCT": "0.5",
        "LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH": "true",
    }
    values.update(extra)
    for k, v in values.items():
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def _clean_repo() -> _FakeRepo:
    repo = _FakeRepo()
    repo.snapshots["account"] = [
        {
            "symbol": "USDT",
            "raw_data": {
                "items": [{"marginCoin": "USDT", "equity": "10000", "available": "9500"}],
            },
        }
    ]
    repo.reconcile_snapshot = {
        "details_json": {"drift": {"total_count": 0, "snapshot_health": {"missing_count": 0, "stale_count": 0}}}
    }
    return repo


def _base_intent() -> ExecutionIntentRequest:
    return ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="sig-truth-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49900",
        take_profit="51000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
            }
        },
    )


def test_live_blocked_when_truth_gate_on_and_drift_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    repo = _clean_repo()
    svc = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    svc.set_truth_state_fn(
        lambda: {
            "truth_channel_ok": True,
            "truth_reason": "ws_connected",
            "drift_blocked": True,
            "drift_total": 3,
            "snapshot_missing": 0,
            "snapshot_stale": 0,
            "ws_connected": True,
            "last_rest_catchup_age_ms": None,
        }
    )
    out = svc.evaluate_intent(_base_intent(), probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "exchange_drift_or_snapshot_unhealthy"


def test_live_blocked_when_no_fresh_truth_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    repo = _clean_repo()
    svc = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    svc.set_truth_state_fn(
        lambda: {
            "truth_channel_ok": False,
            "truth_reason": "no_fresh_exchange_truth_channel",
            "drift_blocked": False,
            "drift_total": 0,
            "snapshot_missing": 0,
            "snapshot_stale": 0,
            "ws_connected": False,
            "last_rest_catchup_age_ms": 999_000,
        }
    )
    out = svc.evaluate_intent(_base_intent(), probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "no_fresh_exchange_truth_channel"


def test_live_allowed_when_ws_truth_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    repo = _clean_repo()
    svc = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    svc.set_truth_state_fn(
        lambda: {
            "truth_channel_ok": True,
            "truth_reason": "ws_connected",
            "drift_blocked": False,
            "drift_total": 0,
            "snapshot_missing": 0,
            "snapshot_stale": 0,
            "ws_connected": True,
            "last_rest_catchup_age_ms": None,
        }
    )
    out = svc.evaluate_intent(_base_intent(), probe_exchange=False)
    assert out["decision_action"] == "live_candidate_recorded"
    assert out["decision_reason"] == "validated_live_candidate"


def test_gate_disabled_ignores_bad_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(
        monkeypatch,
        LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH="false",
    )
    repo = _clean_repo()
    svc = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    svc.set_truth_state_fn(
        lambda: {
            "truth_channel_ok": False,
            "truth_reason": "no_fresh_exchange_truth_channel",
            "drift_blocked": True,
            "drift_total": 9,
            "snapshot_missing": 0,
            "snapshot_stale": 0,
            "ws_connected": False,
            "last_rest_catchup_age_ms": None,
        }
    )
    out = svc.evaluate_intent(_base_intent(), probe_exchange=False)
    assert out["decision_action"] == "live_candidate_recorded"


def test_truth_status_snapshot_reflects_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    svc = LiveExecutionService(settings, _FakeExchangeClient(), _clean_repo())  # type: ignore[arg-type]
    svc.set_truth_state_fn(lambda: {"truth_channel_ok": True, "truth_reason": "ws_connected", "drift_blocked": False})
    snap = svc.truth_status_snapshot()
    assert snap["configured"] is True
    assert snap["gate_enabled"] is True
    assert snap["live_submit_allowed_by_truth"] is True
    assert snap["truth_block_reason"] is None
