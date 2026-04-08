from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any

from news_engine.config import NewsEngineSettings
from news_engine.http_client import http_get_text
from news_engine.models import NewsCandidate
from news_engine.paths import fixtures_dir
from news_engine.timeparse import parse_rss_pub_date

logger = logging.getLogger("news_engine.coindesk_rss")


def load_rss_fixture() -> str:
    return (fixtures_dir() / "coindesk_sample.xml").read_text(encoding="utf-8")


def fetch_rss_text(url: str, settings: NewsEngineSettings) -> str:
    if settings.news_fixture_mode:
        return load_rss_fixture()
    return http_get_text(url, settings)


def parse_rss_items(xml_text: str) -> list[NewsCandidate]:
    out: list[NewsCandidate] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("RSS parse error: %s", exc)
        return out
    channel = root.find("channel")
    if channel is None:
        return out
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = item.findtext("description")
        pub = item.findtext("pubDate")
        if not title or not link:
            continue
        desc_s = desc.strip() if desc else None
        guid = item.findtext("guid")
        out.append(
            NewsCandidate(
                source="coindesk",
                source_item_id=str(guid).strip() if guid else link,
                title=title,
                description=desc_s,
                content=None,
                url=link,
                author=None,
                language=None,
                published_ts_ms=parse_rss_pub_date(pub),
                raw_fragment=_item_to_dict(item),
            )
        )
    return out


def _item_to_dict(item: Any) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for child in list(item):
        tag = child.tag.split("}")[-1]
        if child.text:
            d[tag] = child.text.strip()
    return d


def fetch_coindesk_rss(settings: NewsEngineSettings) -> list[NewsCandidate]:
    try:
        xml_text = fetch_rss_text(settings.coindesk_rss_url, settings)
    except Exception as exc:  # pragma: no cover
        logger.warning("coindesk rss fetch fehlgeschlagen: %s", exc)
        return []
    return parse_rss_items(xml_text)
