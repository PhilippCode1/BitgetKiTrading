"""Live-Broker: bei INFERENCE_TIMEOUT (Fail-Closed) kein handelbares allow_trade / Risk-Engine-Abbruch."""

from __future__ import annotations

import sys
from decimal import Decimal
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
from live_broker.execution.risk_adapter import build_live_trade_risk_decision


class _FakeRepo:
    def list_latest_exchange_snapshots(self, snapshot_type: str, *, symbol=None, limit: int = 200):
        if snapshot_type == "account":
            return [
                {
                    "raw_json": {"equity": "1000", "available": "900", "usdtEquity": "1000"},
                    "margin_coin": "USDT",
                }
            ]
        return []

    def list_live_positions(self) -> list:
        return []


def _settings(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for k, v in {
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
    }.items():
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def _intent() -> ExecutionIntentRequest:
    return ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id=str(uuid4()),
        symbol="ETHUSDT",
        timeframe="5m",
        market_family="futures",
        direction="long",
        order_type="market",
        leverage=7,
        qty_base=Decimal("0.1"),
        entry_price=Decimal("2000"),
        stop_loss=Decimal("1900"),
        take_profit=Decimal("2200"),
        payload={},
    )


def test_risk_decision_blocks_when_governor_universal_has_inference_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(monkeypatch)
    repo = _FakeRepo()
    sp = {
        "trade_action": "allow_trade",
        "governor_universal_hard_block_reasons_json": ["INFERENCE_TIMEOUT"],
    }
    d = build_live_trade_risk_decision(
        settings=s,
        repo=repo,  # type: ignore[arg-type]
        intent=_intent(),
        signal_payload=sp,
        now_ms=1_700_000_000_000,
    )
    assert d.get("trade_action") == "do_not_trade"
    assert d.get("decision_reason") == "INFERENCE_TIMEOUT"
    assert "INFERENCE_TIMEOUT" in (d.get("reasons_json") or [])


def test_risk_decision_blocks_from_source_snapshot_inference_governance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(monkeypatch)
    repo = _FakeRepo()
    sp = {
        "trade_action": "allow_trade",
        "source_snapshot": {
            "inference_governance": {"state": "INFERENCE_TIMEOUT", "fail_closed": True},
        },
    }
    d = build_live_trade_risk_decision(
        settings=s,
        repo=repo,  # type: ignore[arg-type]
        intent=_intent(),
        signal_payload=sp,
        now_ms=1_700_000_000_000,
    )
    assert d.get("trade_action") == "do_not_trade"
    assert d.get("decision_state") == "rejected"
    assert d.get("context", {}).get("inference_fail_closed") is True
