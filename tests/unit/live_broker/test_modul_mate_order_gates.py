"""Unit-Tests: Modul-Mate-Policy-Gate vor Exchange-Submit (LiveBrokerOrderService)."""

from __future__ import annotations

import sys
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
from live_broker.orders.service import LiveBrokerOrderService
from live_broker.private_rest import BitgetRestError


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
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
        ("LIVE_ALLOWED_SYMBOLS", "BTCUSDT"),
        ("LIVE_ALLOWED_MARKET_FAMILIES", "futures"),
        ("LIVE_ALLOWED_PRODUCT_TYPES", "USDT-FUTURES"),
        ("LIVE_REQUIRE_EXCHANGE_HEALTH", "false"),
        ("BITGET_SYMBOL", "BTCUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("BITGET_API_KEY", "k"),
        ("BITGET_API_SECRET", "s"),
        ("BITGET_API_PASSPHRASE", "p"),
        ("RISK_MAX_POSITION_RISK_PCT", "0.5"),
        ("LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH", "false"),
        ("BITGET_DEMO_ENABLED", "false"),
    ):
        monkeypatch.setenv(k, v)
    for dk in (
        "BITGET_DEMO_API_KEY",
        "BITGET_DEMO_API_SECRET",
        "BITGET_DEMO_API_PASSPHRASE",
    ):
        monkeypatch.setenv(dk, "")


def _settings(monkeypatch: pytest.MonkeyPatch, **extra: str) -> LiveBrokerSettings:
    """Wie LiveBrokerSettings(); `extra` ueberschreibt _base_env (z. B. BITGET_DEMO_ENABLED)."""
    _base_env(monkeypatch)
    for k, v in extra.items():
        monkeypatch.setenv(k, v)
    return LiveBrokerSettings()


def _service(settings: LiveBrokerSettings) -> LiveBrokerOrderService:
    return LiveBrokerOrderService(settings, MagicMock(), MagicMock(), bus=None)  # type: ignore[arg-type]


def _pg_context(conn: MagicMock) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    return ctx


def _row(
    *,
    trial: bool = False,
    contract: bool = True,
    admin_live: bool = False,
    subscription: bool = True,
    paused: bool = False,
    suspended: bool = False,
) -> dict[str, bool]:
    return {
        "trial_active": trial,
        "contract_accepted": contract,
        "admin_live_trading_granted": admin_live,
        "subscription_active": subscription,
        "account_paused": paused,
        "account_suspended": suspended,
    }


def test_modul_mate_gate_skipped_when_enforcement_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODUL_MATE_GATE_ENFORCEMENT", raising=False)
    monkeypatch.setenv("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false")
    s = _settings(monkeypatch)
    assert s.modul_mate_gate_enforcement is False
    svc = _service(s)
    with patch("live_broker.orders.service.psycopg.connect") as m:
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)
    m.assert_not_called()


def test_modul_mate_gate_skipped_on_safety_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(monkeypatch, MODUL_MATE_GATE_ENFORCEMENT="true")
    svc = _service(s)
    with patch("live_broker.orders.service.psycopg.connect") as m:
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=True)
    m.assert_not_called()


def test_modul_mate_gate_empty_dsn_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODUL_MATE_GATE_ENFORCEMENT", "false")
    s = _settings(monkeypatch)
    s.modul_mate_gate_enforcement = True
    s.database_url = ""
    svc = _service(s)
    with pytest.raises(BitgetRestError) as ei:
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)
    assert ei.value.classification == "service_misconfigured"
    assert str(ei.value) == "commercial_gates_require_database_url"


def test_live_broker_require_commercial_gates_without_modul_mate_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nur LIVE_BROKER_REQUIRE_COMMERCIAL_GATES=true erzwingt DB-Gate (ohne MODUL_MATE_*)."""
    monkeypatch.delenv("MODUL_MATE_GATE_ENFORCEMENT", raising=False)
    s = _settings(
        monkeypatch,
        LIVE_BROKER_REQUIRE_COMMERCIAL_GATES="true",
        MODUL_MATE_GATE_ENFORCEMENT="false",
    )
    assert s.commercial_gates_enforced_for_exchange_submit is True
    assert s.modul_mate_gate_enforcement is False
    repo = MagicMock()
    svc = LiveBrokerOrderService(s, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row(admin_live=True, contract=True, subscription=True)
    ex_c.fetchone.return_value = (1,)
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)
    repo.record_audit_trail.assert_not_called()


def test_modul_mate_gate_missing_row(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    s = _settings(monkeypatch, MODUL_MATE_GATE_ENFORCEMENT="true")
    svc = LiveBrokerOrderService(s, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = None
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        with pytest.raises(BitgetRestError) as ei:
            svc._assert_modul_mate_policy_allows_exchange_submit(
                allow_safety_bypass=False
            )
    assert ei.value.classification == "policy_blocked"
    assert "modul_mate_gates_missing" in str(ei.value)
    repo.record_audit_trail.assert_called_once()
    call_kw = repo.record_audit_trail.call_args[0][0]
    assert call_kw["category"] == "commercial_gate"
    assert call_kw["action"] == "denied"
    assert (
        call_kw["details_json"].get("policy_violation_reason")
        == "tenant_modul_mate_gates_missing"
    )


def test_modul_mate_live_blocked_for_demo_only_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    s = _settings(
        monkeypatch,
        MODUL_MATE_GATE_ENFORCEMENT="true",
        BITGET_DEMO_ENABLED="false",
    )
    svc = LiveBrokerOrderService(s, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row(admin_live=False, contract=True)
    ex_c.fetchone.return_value = (1,)
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        with pytest.raises(BitgetRestError) as ei:
            svc._assert_modul_mate_policy_allows_exchange_submit(
                allow_safety_bypass=False
            )
    assert str(ei.value) == "modul_mate_live_trading_not_permitted"
    repo.record_audit_trail.assert_called_once()
    assert (
        repo.record_audit_trail.call_args[0][0]["details_json"]["policy_violation_reason"]
        == "live_trading_not_permitted"
    )


def test_modul_mate_live_ok_when_fully_granted(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _settings(
        monkeypatch,
        MODUL_MATE_GATE_ENFORCEMENT="true",
        BITGET_DEMO_ENABLED="false",
    )
    svc = _service(s)
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row(admin_live=True, contract=True, subscription=True)
    ex_c.fetchone.return_value = (1,)
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)


def test_modul_mate_live_blocked_without_tenant_contract_admin_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LIVE: Gates ok, aber kein tenant_contract mit admin_review_complete -> policy_blocked."""
    repo = MagicMock()
    s = _settings(
        monkeypatch,
        MODUL_MATE_GATE_ENFORCEMENT="true",
        BITGET_DEMO_ENABLED="false",
    )
    svc = LiveBrokerOrderService(s, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    conn = MagicMock()
    ex_g = MagicMock()
    ex_c = MagicMock()
    ex_g.fetchone.return_value = _row(admin_live=True, contract=True, subscription=True)
    ex_c.fetchone.return_value = None
    conn.execute.side_effect = live_mode_conn_execute_sequence(ex_g, ex_c)
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        with pytest.raises(BitgetRestError) as ei:
            svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)
    assert "no_active_commercial_contract" in str(ei.value)
    assert ei.value.classification == "policy_blocked"
    repo.record_audit_trail.assert_called_once()
    assert (
        repo.record_audit_trail.call_args[0][0]["details_json"]["policy_violation_reason"]
        == "no_active_commercial_contract"
    )


def test_modul_mate_demo_ok_for_seed_like_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # Nur das Gate verzweigt auf bitget_demo_enabled; volle Settings verbieten
    # EXECUTION_MODE=live + BITGET_DEMO_ENABLED (siehe BaseServiceSettings-Validator).
    s = _settings(monkeypatch, MODUL_MATE_GATE_ENFORCEMENT="true")
    s.bitget_demo_enabled = True
    svc = _service(s)
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = _row(admin_live=False, contract=True)
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        svc._assert_modul_mate_policy_allows_exchange_submit(allow_safety_bypass=False)


def test_modul_mate_demo_blocked_when_no_demo_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = MagicMock()
    s = _settings(monkeypatch, MODUL_MATE_GATE_ENFORCEMENT="true")
    s.bitget_demo_enabled = True
    svc = LiveBrokerOrderService(s, repo, MagicMock(), bus=None)  # type: ignore[arg-type]
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = _row(
        trial=False, contract=False, admin_live=False, subscription=True
    )
    with patch(
        "live_broker.orders.service.psycopg.connect",
        return_value=_pg_context(conn),
    ):
        with pytest.raises(BitgetRestError) as ei:
            svc._assert_modul_mate_policy_allows_exchange_submit(
                allow_safety_bypass=False
            )
    assert str(ei.value) == "modul_mate_demo_trading_not_permitted"
    repo.record_audit_trail.assert_called_once()
    assert (
        repo.record_audit_trail.call_args[0][0]["details_json"]["policy_violation_reason"]
        == "demo_trading_not_permitted"
    )
