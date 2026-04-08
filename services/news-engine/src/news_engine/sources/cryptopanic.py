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

logger = logging.getLogger("news_engine.cryptopanic")


def _load_json_fixture() -> dict[str, Any]:
    path = fixtures_dir() / "cryptopanic_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch_payload(settings: NewsEngineSettings) -> dict[str, Any]:
    if settings.news_fixture_mode:
        return _load_json_fixture()
    if not settings.cryptopanic_api_key:
        logger.info("cryptopanic: kein CRYPTOPANIC_API_KEY, Quelle uebersprungen")
        return {"results": []}
    q = urlencode({"auth_token": settings.cryptopanic_api_key, "public": "true"})
    base = settings.cryptopanic_api_url.rstrip("/")
    url = f"{base}?{q}"
    raw = http_get_text(url, settings)
    return json.loads(raw)


def parse_cryptopanic_results(data: dict[str, Any]) -> list[NewsCandidate]:
    out: list[NewsCandidate] = []
    for row in data.get("results") or []:
        if not isinstance(row, dict):
            continue
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        if not url or not title:
            continue
        sid = row.get("id")
        source_item_id = str(sid) if sid is not None else None
        published = row.get("published_at") or row.get("created_at")
        out.append(
            NewsCandidate(
                source="cryptopanic",
                source_item_id=source_item_id,
                title=title,
                description=None,
                content=None,
                url=url,
                author=None,
                language=None,
                published_ts_ms=parse_iso_to_ms(str(published) if published else None),
                raw_fragment=row,
            )
        )
    return out


def fetch_cryptopanic(settings: NewsEngineSettings) -> list[NewsCandidate]:
    try:
        data = _fetch_payload(settings)
    except Exception as exc:  # pragma: no cover - Netzwerk
        logger.warning("cryptopanic fetch fehlgeschlagen: %s", exc)
        return []
    return parse_cryptopanic_results(data)
