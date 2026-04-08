from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PB_SRC = REPO / "services" / "paper-broker" / "src"
SHARED_SRC = REPO / "shared" / "python" / "src"
for p in (PB_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture(autouse=True)
def _paper_broker_min_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """PaperBrokerSettings verlangt ein Default-Symbol auch ohne produktive Watchlist."""
    monkeypatch.setenv("PAPER_DEFAULT_SYMBOL", "BTCUSDT")
