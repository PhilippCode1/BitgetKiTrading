"""Hartes LIVE-Policy-Gate in LiveExecutionService vor Exchange-I/O (evaluate_intent)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from tests.unit.live_broker.commercial_gate_db_mocks import (
    live_mode_conn_execute_sequence,
)

from live_broker.config import LiveBrokerSettings
from live_broker.exceptions import SecurityException
from live_broker.execution.models import ExecutionIntentRequest
from live_broker.execution.service import LiveExecutionService


def _pg_context(conn: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    return ctx


def _row_live_ok() -> dict:
    return {
        "trial_active": False,
        "contract_accepted": True,
        "admin_live_trading_granted": True,
        "subscription_active": True,
        "account_paused": False,
        "account_suspended": False,
    }


class _SpyExchangeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def build_order_preview(self, intent) -> dict:
        self.calls.append("build_order_preview")
        return {"symbol": intent.symbol, "leverage": intent.leverage}

    def describe(self) -> dict:
        self.calls.append("describe")
        return {"exchange": "bitget"}

    def private_api_configured(self) -> tuple[bool, str]:
        self.calls.append("private_api_configured")
        return True, "ok"

    def probe_exchange(self) -> dict:
        self.calls.append("probe_exchange")
        return {
            "public_api_ok": True,
            "public_detail": "ok",
            "private_api_configured": True,
            "private_detail": "ok",
            "market_snapshot": {},
        }


def _settings_live(monkeypatch: pytest.MonkeyPatch) -> LiveBrokerSettings:
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://t:t@127.0.0.1:5432/t"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("EXECUTION_MODE", "live"),
        ("LIVE_TRADE_ENABLE", "true"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("LIVE_ORDER_SUBMIT_ENABLED", "true"),
        ("LIVE_ALLOW_ORDER_SUBMIT", "true"),
        ("LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH", "false"),
        ("STRATEGY_EXEC_MODE", "auto"),
        ("SHADOW_TRADE_ENABLE", "false"),
        ("REQUIRE_SHADOW_MATCH_BEFORE_LIVE", "false"),
        ("LIVE_ALLOWED_SYMBOLS", "BTCUSDT"),
        ("LIVE_ALLOWED_MARKET_FAMILIES", "futures"),
        ("LIVE_ALLOWED_PRODUCT_TYPES", "USDT-FUTURES"),
        ("LIVE_REQUIRE_EXCHANGE_HEALTH", "false"),
        ("RISK_MAX_POSITION_RISK_PCT", "0.5"),
        ("MODUL_MATE_GATE_ENFORCEMENT", "true"),
        ("BITGET_DEMO_ENABLED", "false"),
        ("BITGET_SYMBOL", "BTCUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
    ):
        monkeypatch.setenv(k, v)
    for k2 in (
        "BITGET_API_KEY",
        "BITGET_API_SECRET",
        "BITGET_API_PASSPHRASE",
    ):
        monkeypatch.setenv(k2, "x")
    return LiveBrokerSettings()


def test_evaluate_intent_no_exchange_calls_when_tenant_contract_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gates erlauben LIVE, aber app.tenant_contract hat kein admin_review_complete — Abbruch vor I/O."""
    from tests.unit.live_broker.test_execution_service import _FakeRepo

    settings = _settings_live(monkeypatch)
    assert settings.commercial_gates_enforced_for_exchange_submit is True
    ex = _SpyExchangeClient()
    repo = _FakeRepo()
    # Kein vollstaendiger Risk/Exit-Pfad noetig — Policy scheitert zuerst.
    service = LiveExecutionService(settings, ex, repo, catalog=None)  # type: ignore[arg-type]

    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row_live_ok()
    ex_c.fetchone.return_value = None
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)

    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="nocc-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.01",
        entry_price="100000",
        stop_loss="90000",
        take_profit="120000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "meta_trade_lane": "candidate_for_live",
                "decision_state": "accepted",
                "shadow_divergence_0_1": 0.0,
                "analysis_ts_ms": now_ms,
            }
        },
    )
    with patch("live_broker.execution.service.psycopg.connect", return_value=_pg_context(conn)):
        with pytest.raises(SecurityException) as ei:
            service.evaluate_intent(intent, probe_exchange=True)
    assert ei.value.reason == "no_active_commercial_contract"
    assert ex.calls == []
    assert len(repo.audit_trails) == 1
    assert repo.audit_trails[0].get("action") == "SECURITY_INCIDENT_ATTEMPT"
    assert (repo.audit_trails[0].get("details_json") or {}).get("incident_type") == (
        "SECURITY_INCIDENT_ATTEMPT"
    )


def test_evaluate_intent_proceeds_when_contract_and_gates_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.live_broker.test_execution_service import (
        _repo_with_clean_live_snapshots,
    )

    settings = _settings_live(monkeypatch)
    ex = _SpyExchangeClient()
    repo = _repo_with_clean_live_snapshots()
    service = LiveExecutionService(settings, ex, repo, catalog=None)  # type: ignore[arg-type]
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row_live_ok()
    ex_c.fetchone.return_value = (1,)
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="ok-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.01",
        entry_price="100000",
        stop_loss="90000",
        take_profit="120000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "meta_trade_lane": "candidate_for_live",
                "decision_state": "accepted",
                "rejection_state": False,
                "shadow_divergence_0_1": 0.0,
                "analysis_ts_ms": now_ms,
                "expected_return_bps": 10.0,
                "expected_mae_bps": 10.0,
                "expected_mfe_bps": 20.0,
            }
        },
    )
    with patch("live_broker.execution.service.psycopg.connect", return_value=_pg_context(conn)):
        service.evaluate_intent(intent, probe_exchange=True)
    assert "build_order_preview" in ex.calls


def _row_live_gates_demo_only() -> dict:
    """admin_live false -> live_trading_not_permitted trotz Contract."""
    return {
        "trial_active": False,
        "contract_accepted": True,
        "admin_live_trading_granted": False,
        "subscription_active": True,
        "account_paused": False,
        "account_suspended": False,
    }


def test_evaluate_intent_no_bitget_when_live_trading_forbidden_in_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gates + Vertrag, aber product_policy: kein Live — Bitget-Client unberuehrt."""
    from tests.unit.live_broker.test_execution_service import _FakeRepo

    settings = _settings_live(monkeypatch)
    ex = _SpyExchangeClient()
    repo = _FakeRepo()
    service = LiveExecutionService(settings, ex, repo, catalog=None)  # type: ignore[arg-type]
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row_live_gates_demo_only()
    ex_c.fetchone.return_value = (1,)
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    now_ms = int(time.time() * 1000)
    intent = ExecutionIntentRequest(
        source_service="signal-engine",
        signal_id="ltd-1",
        symbol="BTCUSDT",
        direction="long",
        requested_runtime_mode="live",
        leverage=12,
        qty_base="0.01",
        entry_price="100000",
        stop_loss="90000",
        take_profit="120000",
        payload={
            "signal_payload": {
                "trade_action": "allow_trade",
                "meta_trade_lane": "candidate_for_live",
                "decision_state": "accepted",
                "shadow_divergence_0_1": 0.0,
                "analysis_ts_ms": now_ms,
            }
        },
    )
    with patch("live_broker.execution.service.psycopg.connect", return_value=_pg_context(conn)):
        with pytest.raises(SecurityException) as ei:
            service.evaluate_intent(intent, probe_exchange=True)
    assert ei.value.reason == "live_trading_not_permitted"
    assert ex.calls == []
    assert any(
        t.get("action") == "SECURITY_INCIDENT_ATTEMPT" for t in repo.audit_trails
    )
