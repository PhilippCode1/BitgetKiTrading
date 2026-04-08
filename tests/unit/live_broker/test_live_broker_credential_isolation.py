"""Prompt 6: Demo/Live-Credential-Isolation im LiveBrokerSettings."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from live_broker.config import LiveBrokerSettings


def _base_demo_ws(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITGET_DEMO_WS_PUBLIC_URL", "wss://wspap.bitget.com/v2/ws/public")
    monkeypatch.setenv("BITGET_DEMO_WS_PRIVATE_URL", "wss://wspap.bitget.com/v2/ws/private")


def _minimal_live_broker_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in (
        ("APP_ENV", "test"),
        ("PRODUCTION", "false"),
        ("DATABASE_URL", "postgresql://t:t@127.0.0.1:5432/t"),
        ("REDIS_URL", "redis://127.0.0.1:6379/0"),
        ("LIVE_BROKER_ENABLED", "true"),
        ("BITGET_SYMBOL", "BTCUSDT"),
        ("BITGET_MARKET_FAMILY", "futures"),
        ("BITGET_PRODUCT_TYPE", "USDT-FUTURES"),
        ("BITGET_MARGIN_COIN", "USDT"),
        ("LIVE_BROKER_BASE_URL", "https://example.invalid"),
    ):
        monkeypatch.setenv(k, v)


def test_demo_mode_rejects_parallel_live_credentials_when_private_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _minimal_live_broker_env(monkeypatch)
    _base_demo_ws(monkeypatch)
    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "true")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "dk")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "ds")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "dp")
    monkeypatch.setenv("BITGET_API_KEY", "lk")
    monkeypatch.setenv("BITGET_API_SECRET", "ls")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "lp")
    with pytest.raises(ValueError, match="BITGET_API_KEY"):
        LiveBrokerSettings()


def test_shadow_private_path_rejects_demo_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_live_broker_env(monkeypatch)
    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    monkeypatch.setenv("BITGET_API_KEY", "lk")
    monkeypatch.setenv("BITGET_API_SECRET", "ls")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "lp")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "dk")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "ds")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "dp")
    with pytest.raises(ValueError, match="BITGET_DEMO_API_KEY"):
        LiveBrokerSettings()


def test_relax_isolation_allows_both_sets_on_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    _minimal_live_broker_env(monkeypatch)
    monkeypatch.setenv("EXECUTION_MODE", "shadow")
    monkeypatch.setenv("SHADOW_TRADE_ENABLE", "true")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    monkeypatch.setenv("BITGET_RELAX_CREDENTIAL_ISOLATION", "true")
    monkeypatch.setenv("BITGET_API_KEY", "lk")
    monkeypatch.setenv("BITGET_API_SECRET", "ls")
    monkeypatch.setenv("BITGET_API_PASSPHRASE", "lp")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "dk")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "ds")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "dp")
    s = LiveBrokerSettings()
    assert s.bitget_relax_credential_isolation is True
