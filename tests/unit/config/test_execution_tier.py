from __future__ import annotations

import pytest
from config.execution_tier import build_execution_tier_payload
from config.settings import BaseServiceSettings


def _base(monkeypatch: pytest.MonkeyPatch, **extra: str) -> None:
    env = {
        "APP_ENV": "test",
        "PRODUCTION": "false",
        "EXECUTION_MODE": "paper",
        "SHADOW_TRADE_ENABLE": "false",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "false",
        "STRATEGY_EXEC_MODE": "manual",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "75",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "BITGET_DEMO_ENABLED": "false",
    }
    env.update(extra)
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_tier_paper_development(monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch)
    s = BaseServiceSettings()
    tier = build_execution_tier_payload(s)
    assert tier["trading_plane"] == "paper"
    assert tier["deployment"] == "development"
    assert tier["bitget_demo_enabled"] is False


def test_tier_exchange_sandbox_overrides_paper_label(monkeypatch: pytest.MonkeyPatch) -> None:
    _base(monkeypatch, BITGET_DEMO_ENABLED="true")
    s = BaseServiceSettings()
    tier = build_execution_tier_payload(s)
    assert tier["trading_plane"] == "exchange_sandbox"
    assert tier["bitget_demo_enabled"] is True


def test_tier_automated_live_orders(monkeypatch: pytest.MonkeyPatch) -> None:
    _base(
        monkeypatch,
        EXECUTION_MODE="live",
        LIVE_BROKER_ENABLED="true",
        LIVE_TRADE_ENABLE="true",
        SHADOW_TRADE_ENABLE="false",
        STRATEGY_EXEC_MODE="auto",
    )
    s = BaseServiceSettings()
    tier = build_execution_tier_payload(s)
    assert tier["trading_plane"] == "live"
    assert tier["automated_live_orders_enabled"] is True
