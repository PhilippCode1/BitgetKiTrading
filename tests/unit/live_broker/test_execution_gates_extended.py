"""Paper-Mode-Gate, 7x-Freigabe und Leverage-Grenzen (7..75) gegen ExecutionIntent / Signal-Pfad."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch
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
from shared_py.eventbus import EventEnvelope


@pytest.fixture(autouse=True)
def _stub_live_m604_policy_for_unit_tests() -> object:
    with patch.object(
        LiveExecutionService,
        "_assert_db_live_execution_policy",
        lambda _self: None,
    ):
        yield


class _FakeExchangeClient:
    def build_order_preview(self, intent):
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self):
        return {"exchange": "bitget"}

    def private_api_configured(self):
        return True, "ok"


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshots: dict[str, list] = {"account": [], "positions": []}
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


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    values = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "EXECUTION_MODE": "shadow",
        "STRATEGY_EXEC_MODE": "auto",
        "SHADOW_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_TRADE_ENABLE": "false",
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
        "details_json": {"drift": {"snapshot_health": {"missing_types": [], "stale_types": []}}}
    }
    return repo


def test_handle_signal_event_ignored_in_paper_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, EXECUTION_MODE="paper", SHADOW_TRADE_ENABLE="false")
    service = LiveExecutionService(settings, _FakeExchangeClient(), _clean_repo())  # type: ignore[arg-type]
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={"signal_id": "p1", "direction": "long", "trade_action": "allow_trade"},
    )
    out = service.handle_signal_event(env)
    assert out["decision_action"] == "ignored"
    assert out["decision_reason"] == "paper_mode_routes_to_paper_broker"


def test_decision_blocks_leverage_7_without_approval_before_submit_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(monkeypatch, RISK_REQUIRE_7X_APPROVAL="true")
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="l7",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="shadow",
        leverage=7,
        approved_7x=False,
        qty_base="0.001",
        entry_price="50000",
            stop_loss="49550",
        take_profit="52000",
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
                "recommended_leverage": 7,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "missing_7x_approval"


def test_decision_allows_leverage_7_when_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        RISK_REQUIRE_7X_APPROVAL="true",
    )
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="l7ok",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=7,
        approved_7x=True,
        qty_base="0.001",
        entry_price="50000",
            stop_loss="49550",
        take_profit="52000",
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
                "recommended_leverage": 7,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "live_candidate_recorded"
    assert out["decision_reason"] == "validated_live_candidate"


def test_live_submit_blocked_when_signal_carries_live_execution_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
    )
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="live-pol",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        approved_7x=True,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49550",
        take_profit="52000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "decision_state": "accepted",
                "rejection_state": False,
                "meta_trade_lane": "candidate_for_live",
                "live_execution_block_reasons_json": [
                    "risk_governor_margin_utilization_exceeded",
                ],
                "signal_strength_0_100": 90,
                "probability_0_1": 0.8,
                "risk_score_0_100": 80,
                "expected_return_bps": 14.0,
                "expected_mae_bps": 15.0,
                "expected_mfe_bps": 28.0,
                "allowed_leverage": 12,
                "recommended_leverage": 12,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "portfolio_live_execution_policy"


def test_execution_intent_rejects_leverage_below_policy_minimum() -> None:
    with pytest.raises(ValueError, match="7..75"):
        ExecutionIntentRequest(
            symbol="BTCUSDT",
            direction="long",
            leverage=6,
            qty_base="0.01",
            entry_price="1",
            stop_loss="0.5",
            take_profit="2",
        )


def test_execution_intent_rejects_leverage_above_policy_maximum() -> None:
    with pytest.raises(ValueError, match="7..75"):
        ExecutionIntentRequest(
            symbol="BTCUSDT",
            direction="long",
            leverage=76,
            qty_base="0.01",
            entry_price="1",
            stop_loss="0.5",
            take_profit="2",
        )


def test_live_intent_blocked_when_execution_mode_not_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="shadow",
        SHADOW_TRADE_ENABLE="true",
        LIVE_TRADE_ENABLE="false",
        STRATEGY_EXEC_MODE="auto",
    )
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="live-to-shadow",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=7,
        approved_7x=True,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49550",
        take_profit="52000",
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
                "recommended_leverage": 7,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "live_submit_disabled"


def test_live_intent_blocks_when_live_trade_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="false",
        STRATEGY_EXEC_MODE="auto",
    )
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="live-disabled",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=7,
        approved_7x=True,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49550",
        take_profit="52000",
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
                "recommended_leverage": 7,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "live_submit_disabled"


def test_live_intent_blocks_when_start_ramp_leverage_cap_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(
        monkeypatch,
        EXECUTION_MODE="live",
        SHADOW_TRADE_ENABLE="false",
        LIVE_TRADE_ENABLE="true",
        STRATEGY_EXEC_MODE="auto",
        RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE="7",
    )
    repo = _clean_repo()
    service = LiveExecutionService(settings, _FakeExchangeClient(), repo)  # type: ignore[arg-type]
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="start-ramp-lev",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=8,
        approved_7x=True,
        qty_base="0.001",
        entry_price="50000",
        stop_loss="49550",
        take_profit="52000",
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
                "recommended_leverage": 8,
            },
            "signal_allowed_leverage": 12,
            "signal_trade_action": "allow_trade",
        },
    )
    out = service.evaluate_intent(intent, probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "live_ramp_leverage_cap_exceeded"
