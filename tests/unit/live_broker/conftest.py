"""
Live-Broker-Unit-Tests: Host-ENV (z. B. .env.local mit BITGET_DEMO_ENABLED=true) darf
EXECUTION_MODE=live nicht mit Demo-Flag kollidieren lassen — Settings-Validator schlaegt sonst fehl.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _live_broker_unit_quiet_demo_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "false")
    monkeypatch.setenv("BITGET_DEMO_API_KEY", "")
    monkeypatch.setenv("BITGET_DEMO_API_SECRET", "")
    monkeypatch.setenv("BITGET_DEMO_API_PASSPHRASE", "")
    monkeypatch.setenv("LIVE_BROKER_REQUIRE_COMMERCIAL_GATES", "false")
    monkeypatch.setenv("MODUL_MATE_GATE_ENFORCEMENT", "false")
