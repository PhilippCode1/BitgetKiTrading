"""
Config-Unit-Tests: .env.local kann Platzhalter fuer Watchlist/Universe enthalten.
OS-ENV schlaegt Dotenv, aber ohne explizite BITGET_*-Variablen wuerden inkonsistente
Datei-Werte die Validierung vor den eigentlichen Test-Assertions ausloesen.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _coherent_bitget_universe_and_watchlist(monkeypatch: pytest.MonkeyPatch) -> None:
    # Platzhalter aus .env.local (Discovery) wuerden sonst vor den Test-Assertions scheitern.
    monkeypatch.setenv("BITGET_UNIVERSE_SYMBOLS", "BTCUSDT,ETHUSDT")
    monkeypatch.setenv("BITGET_WATCHLIST_SYMBOLS", "BTCUSDT,ETHUSDT")
    monkeypatch.setenv("FEATURE_SCOPE_SYMBOLS", "BTCUSDT,ETHUSDT")
    monkeypatch.setenv("SIGNAL_SCOPE_SYMBOLS", "BTCUSDT,ETHUSDT")
