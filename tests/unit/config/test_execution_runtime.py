from __future__ import annotations

import pytest
from config.execution_runtime import build_execution_runtime_snapshot
from config.settings import BaseServiceSettings


def _minimal_env(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    base = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "EXECUTION_MODE": "paper",
        "BITGET_DEMO_ENABLED": "false",
        "SHADOW_TRADE_ENABLE": "false",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "false",
        "STRATEGY_EXEC_MODE": "manual",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "75",
        "LIVE_KILL_SWITCH_ENABLED": "true",
    }
    base.update(extra)
    for k, v in base.items():
        monkeypatch.setenv(k, v)


def test_execution_runtime_snapshot_paper(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch)
    s = BaseServiceSettings()
    snap = build_execution_runtime_snapshot(s)
    assert snap["schema_version"] == 2
    assert snap["execution_tier"]["trading_plane"] == "paper"
    assert snap["execution_tier"]["deployment"] == "development"
    assert snap["primary_mode"] == "paper"
    assert snap["paths"]["paper_path_active"] is True
    assert snap["capabilities"]["live_broker_consumes_signals"] is False
    assert snap["capabilities"]["exchange_order_submit_automated"] is False
    assert snap["configuration"]["app_env"] == "test"
    assert snap["configuration"]["market_universe"]["market_families"] == [
        "spot",
        "margin",
        "futures",
    ]


def test_execution_runtime_snapshot_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(
        monkeypatch,
        EXECUTION_MODE="shadow",
        SHADOW_TRADE_ENABLE="true",
        LIVE_BROKER_ENABLED="true",
    )
    s = BaseServiceSettings()
    snap = build_execution_runtime_snapshot(s)
    assert snap["primary_mode"] == "shadow"
    assert snap["paths"]["shadow_path_active"] is True
    assert snap["capabilities"]["shadow_decision_journal"] is True
    assert snap["capabilities"]["exchange_order_submit_automated"] is False
    assert snap["configuration"]["market_universe"]["catalog_policy"]["unknown_instrument_action"] == "no_trade_no_subscribe"


def test_execution_runtime_live_requires_auto_for_automated_submit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _minimal_env(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_BROKER_ENABLED="true",
        LIVE_TRADE_ENABLE="true",
        SHADOW_TRADE_ENABLE="false",
        STRATEGY_EXEC_MODE="manual",
    )
    s = BaseServiceSettings()
    snap = build_execution_runtime_snapshot(s)
    assert snap["live_release"]["env_allows_live_orders"] is True
    assert snap["live_release"]["fully_released_for_automated_exchange_orders"] is False
    assert snap["live_release"]["manual_strategy_holds_live_firewall"] is True

    monkeypatch.setenv("STRATEGY_EXEC_MODE", "auto")
    s2 = BaseServiceSettings()
    snap2 = build_execution_runtime_snapshot(s2)
    assert snap2["live_release"]["fully_released_for_automated_exchange_orders"] is True


def test_shadow_mode_without_shadow_flag_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_env(monkeypatch, EXECUTION_MODE="shadow", SHADOW_TRADE_ENABLE="false")
    with pytest.raises(ValueError, match="EXECUTION_MODE=shadow"):
        BaseServiceSettings()
