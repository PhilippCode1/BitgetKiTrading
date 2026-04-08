from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NewsCandidate:
    """Normalisiertes Roh-Item vor DB-Insert."""

    source: str  # cryptopanic | newsapi | coindesk | gdelt
    source_item_id: str | None
    title: str
    description: str | None
    content: str | None
    url: str
    author: str | None
    language: str | None
    published_ts_ms: int | None
    raw_fragment: dict[str, Any] = field(default_factory=dict)
    ingest_channel: str | None = None  # z.B. top_headlines fuer NewsAPI Top-Headlines
