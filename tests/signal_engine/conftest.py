from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture
def signal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    from signal_engine.config import SignalEngineSettings

    return SignalEngineSettings()
