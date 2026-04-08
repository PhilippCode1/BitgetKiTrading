"""Safety-Latch blockiert signalgetriebenen Live-Pfad; Release ueber Audit-Kette."""

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
from live_broker.orders.models import SafetyLatchReleaseRequest
from live_broker.orders.service import LiveBrokerOrderService


class _FakeEx:
    def build_order_preview(self, intent):
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self):
        return {"exchange": "bitget"}

    def private_api_configured(self):
        return True, "ok"


class _FakeRepo:
    def __init__(self) -> None:
        self.snapshots: dict[str, list] = {}
        self.audit: list[dict] = []
        self.reconcile_snapshot: dict | None = {
            "details_json": {"drift": {"total_count": 0, "snapshot_health": {"missing_count": 0, "stale_count": 0}}}
        }

    def record_execution_decision(self, record: dict):
        return {**record, "execution_id": str(uuid4())}

    def record_execution_risk_snapshot(self, execution_decision_id: str, risk_decision: dict) -> None:
        return None

    def record_shadow_live_assessment(self, **kwargs) -> None:
        return None

    def list_latest_exchange_snapshots(self, snapshot_type: str, *, symbol=None, limit: int = 200):
        return self.snapshots.get(snapshot_type, [])

    def list_exchange_snapshots_since(self, snapshot_type: str, *, since_ts_ms: int, limit: int = 5000):
        return []

    def latest_reconcile_snapshot(self):
        return self.reconcile_snapshot

    def fetch_online_drift_state(self):
        return None

    def safety_latch_is_active(self) -> bool:
        for row in reversed(self.audit):
            if row.get("category") == "safety_latch":
                return row.get("action") == "arm"
        return False

    def record_audit_trail(self, record: dict) -> dict:
        r = dict(record)
        self.audit.append(r)
        return r


def _live_settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://t:t@127.0.0.1:5432/t"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("EXECUTION_MODE", "live"),
        ("STRATEGY_EXEC_MODE", "auto"),
        ("SHADOW_TRADE_ENABLE", "false"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("LIVE_TRADE_ENABLE", "true"),
        ("LIVE_ALLOWED_SYMBOLS", "BTCUSDT,ETHUSDT"),
        ("LIVE_ALLOWED_MARKET_FAMILIES", "futures,spot,margin"),
        ("LIVE_ALLOWED_PRODUCT_TYPES", "USDT-FUTURES"),
        ("LIVE_REQUIRE_EXCHANGE_HEALTH", "false"),
        ("BITGET_SYMBOL", "ETHUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("BITGET_API_KEY", "k"),
        ("BITGET_API_SECRET", "s"),
        ("BITGET_API_PASSPHRASE", "p"),
        ("RISK_MAX_POSITION_RISK_PCT", "0.5"),
        ("LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH", "false"),
    ):
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def _intent() -> ExecutionIntentRequest:
    return ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="s1",
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


def test_live_intent_blocked_when_safety_latch_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    repo = _FakeRepo()
    repo.snapshots = {
        "account": [
            {
                "symbol": "USDT",
                "raw_data": {"items": [{"marginCoin": "USDT", "equity": "10000", "available": "9500"}]},
            }
        ]
    }
    repo.audit.append(
        {
            "category": "safety_latch",
            "action": "arm",
            "severity": "critical",
            "scope": "service",
            "scope_key": "reconcile",
            "source": "reconcile",
        }
    )
    svc = LiveExecutionService(settings, _FakeEx(), repo)  # type: ignore[arg-type]
    out = svc.evaluate_intent(_intent(), probe_exchange=False)
    assert out["decision_action"] == "blocked"
    assert out["decision_reason"] == "live_safety_latch_active"


def test_order_service_release_safety_latch_clears_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _live_settings(monkeypatch)
    repo = _FakeRepo()
    repo.audit.append({"category": "safety_latch", "action": "arm", "source": "reconcile"})
    # LiveBrokerOrderService braucht private client nur fuer cancel-all — hier nicht aufgerufen
    from unittest.mock import MagicMock

    osvc = LiveBrokerOrderService(settings, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    assert repo.safety_latch_is_active() is True
    osvc.release_safety_latch(SafetyLatchReleaseRequest(reason="ops cleared after review"))
    assert repo.safety_latch_is_active() is False
