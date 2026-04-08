from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

from news_engine.config import NewsEngineSettings
from news_engine.http_client import http_get_text
from news_engine.models import NewsCandidate
from news_engine.paths import fixtures_dir
from news_engine.timeparse import parse_gdelt_seendate, parse_iso_to_ms

logger = logging.getLogger("news_engine.gdelt")


def _load_fixture() -> dict[str, Any]:
    path = fixtures_dir() / "gdelt_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_article_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("articles", "data", "docs"):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def _row_to_candidate(row: dict[str, Any]) -> NewsCandidate | None:
    url = str(row.get("url") or row.get("socialimage") or "").strip()
    title = str(row.get("title") or row.get("seotitle") or "").strip()
    if not url or not title:
        return None
    seendate = row.get("seendate") or row.get("seen")
    pub_ms = parse_gdelt_seendate(str(seendate) if seendate else None)
    if pub_ms is None:
        pub_ms = parse_iso_to_ms(str(row.get("datetime") or ""))
    lang = row.get("language") or row.get("lang")
    return NewsCandidate(
        source="gdelt",
        source_item_id=str(seendate) if seendate else None,
        title=title,
        description=None,
        content=None,
        url=url,
        author=None,
        language=str(lang) if lang else None,
        published_ts_ms=pub_ms,
        raw_fragment=row,
    )


def build_gdelt_url(settings: NewsEngineSettings) -> str:
    kws = settings.keyword_list()
    if not kws:
        q = "bitcoin OR btc"
    else:
        q = "(" + " OR ".join(kws) + ")"
    params = urlencode(
        {
            "query": q,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": "40",
        }
    )
    base = settings.gdelt_doc_api_base.split("?")[0].rstrip("/")
    return f"{base}?{params}"


def fetch_gdelt_doc(settings: NewsEngineSettings) -> list[NewsCandidate]:
    if settings.news_fixture_mode:
        data = _load_fixture()
    else:
        url = build_gdelt_url(settings)
        try:
            raw = http_get_text(url, settings)
            data = json.loads(raw)
        except Exception as exc:  # pragma: no cover
            logger.warning("gdelt doc fetch fehlgeschlagen: %s", exc)
            return []
    rows = _extract_article_list(data)
    return [c for r in rows if (c := _row_to_candidate(r)) is not None]
