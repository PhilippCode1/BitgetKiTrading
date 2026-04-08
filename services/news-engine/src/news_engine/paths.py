from __future__ import annotations

from pathlib import Path


def news_engine_root() -> Path:
    """Verzeichnis services/news-engine (mit fixtures/, pyproject.toml)."""
    return Path(__file__).resolve().parents[2]


def fixtures_dir() -> Path:
    return news_engine_root() / "fixtures"
