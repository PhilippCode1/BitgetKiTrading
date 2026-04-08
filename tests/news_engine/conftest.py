from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
NE_SRC = REPO / "services" / "news-engine" / "src"
SHARED_SRC = REPO / "shared" / "python" / "src"
for p in (NE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


@pytest.fixture
def news_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@127.0.0.1:5432/test")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "true")
    from news_engine.config import NewsEngineSettings

    return NewsEngineSettings()
