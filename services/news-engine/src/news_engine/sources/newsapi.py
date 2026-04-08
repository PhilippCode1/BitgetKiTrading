from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

from news_engine.config import NewsEngineSettings
from news_engine.http_client import http_get_text
from news_engine.models import NewsCandidate
from news_engine.paths import fixtures_dir
from news_engine.timeparse import parse_iso_to_ms

logger = logging.getLogger("news_engine.newsapi")


def _load_fixture() -> dict[str, Any]:
    path = fixtures_dir() / "newsapi_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _articles_from_payload(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("articles"), list):
        return [a for a in data["articles"] if isinstance(a, dict)]
    return []


def _row_to_candidate(
    row: dict[str, Any], *, ingest_channel: str | None = None
) -> NewsCandidate | None:
    url = str(row.get("url") or "").strip()
    title = str(row.get("title") or "").strip()
    if not url or not title:
        return None
    published = row.get("publishedAt") or row.get("published_at")
    author = row.get("author")
    desc = row.get("description")
    content = row.get("content")
    return NewsCandidate(
        source="newsapi",
        source_item_id=None,
        title=title,
        description=str(desc).strip() if desc else None,
        content=str(content).strip() if content else None,
        url=url,
        author=str(author).strip() if author else None,
        language=str(row.get("language")).strip() if row.get("language") else None,
        published_ts_ms=parse_iso_to_ms(str(published) if published else None),
        raw_fragment=row,
        ingest_channel=ingest_channel,
    )


def fetch_newsapi_top(settings: NewsEngineSettings) -> list[NewsCandidate]:
    if settings.news_fixture_mode:
        rows = _articles_from_payload(_load_fixture())
        return [
            c
            for r in rows
            if (c := _row_to_candidate(r, ingest_channel="top_headlines")) is not None
        ]
    if not settings.newsapi_api_key:
        logger.info("newsapi top-headlines: kein NEWSAPI_API_KEY")
        return []
    q = "bitcoin OR btc OR crypto OR etf OR fed OR sec"
    pdict: dict[str, str] = {
        "q": q,
        "language": "en",
        "pageSize": "20",
        "apiKey": settings.newsapi_api_key,
    }
    cc = (settings.newsapi_top_country or "").strip()
    if cc:
        pdict["country"] = cc
    params = urlencode(pdict)
    url = f"https://newsapi.org/v2/top-headlines?{params}"
    try:
        data = json.loads(http_get_text(url, settings))
    except Exception as exc:  # pragma: no cover
        logger.warning("newsapi top-headlines fehlgeschlagen: %s", exc)
        return []
    return [
        c
        for r in _articles_from_payload(data)
        if (c := _row_to_candidate(r, ingest_channel="top_headlines")) is not None
    ]


def fetch_newsapi_everything(settings: NewsEngineSettings) -> list[NewsCandidate]:
    if settings.news_fixture_mode:
        # gleiche Fixture-Datei, anderer semantischer Pfad — reicht fuer Tests
        rows = _articles_from_payload(_load_fixture())
        return [c for r in rows if (c := _row_to_candidate(r)) is not None]
    if not settings.newsapi_api_key:
        logger.info("newsapi everything: kein NEWSAPI_API_KEY")
        return []
    q = "bitcoin OR btc OR ETF OR SEC OR fed OR regulation"
    params = urlencode(
        {
            "q": q,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": "20",
            "apiKey": settings.newsapi_api_key,
        }
    )
    url = f"https://newsapi.org/v2/everything?{params}"
    try:
        data = json.loads(http_get_text(url, settings))
    except Exception as exc:  # pragma: no cover
        logger.warning("newsapi everything fehlgeschlagen: %s", exc)
        return []
    return [c for r in _articles_from_payload(data) if (c := _row_to_candidate(r)) is not None]
