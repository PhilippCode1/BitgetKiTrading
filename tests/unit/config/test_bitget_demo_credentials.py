from __future__ import annotations

import pytest

from shared_py.bitget.config import BitgetSettings


def test_bitget_demo_requires_demo_api_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ohne eindeutiges Non-Live: Host-ENV (EXECUTION_MODE=live) würde zuerst scheitern
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    monkeypatch.setenv("LIVE_BROKER_ENABLED", "false")
    monkeypatch.setenv("LIVE_TRADE_ENABLE", "false")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "true")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "")
    with pytest.raises(ValueError, match="BITGET_DEMO_API_KEY"):
        BitgetSettings()
