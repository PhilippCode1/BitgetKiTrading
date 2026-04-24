"""Toxic-Flow-Guard: VPIN aus Redis bzw. Risk-Entscheidung (RISK_VPIN_HALT)."""

from __future__ import annotations

import sys
from decimal import Decimal
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
from live_broker.execution.risk_adapter import RISK_VPIN_HALT, build_live_trade_risk_decision
from live_broker.execution.service import LiveExecutionService


class _FakeRepoVpin:
    def list_latest_exchange_snapshots(self, snapshot_type: str, *, symbol=None, limit: int = 200):
        if snapshot_type == "account":
            return [
                {
                    "raw_data": {
                        "items": [
                            {
                                "marginCoin": "USDT",
                                "equity": "10000",
                                "available": "9500",
                                "usdtEquity": "10000",
                            }
                        ]
                    },
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


def _allowing_signal_payload() -> dict:
    return {
        "trade_action": "allow_trade",
        "allowed_leverage": 7,
        "recommended_leverage": 7,
    }


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
        payload={"signal_payload": _allowing_signal_payload()},
    )


def test_risk_adapter_rejects_at_vpin_0_9_despite_favorable_margin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DoD: VPIN 0,9 -> do_not_trade (RISK_VPIN_HALT), Hebel/Marge unkritisch."""
    s = _settings(monkeypatch)
    repo = _FakeRepoVpin()
    d = build_live_trade_risk_decision(
        settings=s,
        repo=repo,  # type: ignore[arg-type]
        intent=_intent(),
        signal_payload=_allowing_signal_payload(),
        now_ms=1_700_000_000_000,
        market_vpin_score_0_1=0.9,
    )
    assert d.get("trade_action") == "do_not_trade"
    assert d.get("decision_reason") == RISK_VPIN_HALT
    assert RISK_VPIN_HALT in (d.get("reasons_json") or [])


class _FakeEx:
    def build_order_preview(self, intent) -> dict:
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self) -> dict:
        return {"exchange": "bitget"}

    def private_api_configured(self) -> tuple[bool, str]:
        return True, "ok"


class _RepoEval:
    def __init__(self) -> None:
        self.journal_phases: list[str] = []
        self.risk_primary: str | None = None

    def record_execution_decision(self, record: dict) -> dict:
        eid = str(record.get("execution_id") or uuid4())
        return {**record, "execution_id": eid}

    def record_execution_journal(self, record: dict) -> dict:
        self.journal_phases.append(str(record.get("phase") or ""))
        return {"journal_id": 1, **record}

    def record_execution_risk_snapshot(
        self, execution_decision_id: str, risk_decision: dict
    ) -> None:
        self.risk_primary = str(risk_decision.get("decision_reason") or "")

    def list_latest_exchange_snapshots(self, *a, **k):
        return _FakeRepoVpin().list_latest_exchange_snapshots(*a, **k)

    def list_live_positions(self) -> list:
        return []


def test_evaluate_intent_blocks_when_redis_vpin_0_9(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _settings(monkeypatch)
    repo = _RepoEval()
    with (
        patch.object(
            LiveExecutionService,
            "_assert_db_live_execution_policy",
            lambda _self: None,
        ),
        patch(
            "live_broker.execution.service.read_market_vpin_score_0_1",
            return_value=0.9,
        ),
    ):
        svc = LiveExecutionService(s, _FakeEx(), repo)  # type: ignore[arg-type]
        out = svc.evaluate_intent(_intent(), probe_exchange=False)
    assert out.get("decision_action") == "blocked"
    assert out.get("decision_reason") == RISK_VPIN_HALT
    assert RISK_VPIN_HALT in repo.journal_phases
    assert repo.risk_primary == RISK_VPIN_HALT
