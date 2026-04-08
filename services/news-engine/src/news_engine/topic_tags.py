"""Heuristische Themen-Tags fuer Symbol-/Makro-Zuordnung (regelbasiert, kein LLM)."""

from __future__ import annotations

import re

from news_engine.models import NewsCandidate


def infer_topic_tags(candidate: NewsCandidate) -> list[str]:
    parts = [
        candidate.title or "",
        candidate.description or "",
        candidate.content or "",
    ]
    blob = " ".join(parts).lower()
    tags: list[str] = []
    if any(
        x in blob
        for x in (
            "bitcoin",
            "btc ",
            " btc",
            "btc,",
        )
    ) or _word_btc(blob):
        tags.append("btc")
    if any(x in blob for x in ("ethereum", " ether", "eth ", " eth,", "defi")):
        tags.append("eth_defi")
    if any(x in blob for x in ("fed", "fomc", "cpi", "inflation", "interest rate", "rates")):
        tags.append("macro")
    if any(x in blob for x in ("sec", "etf", "regulation", "lawsuit", "ban ")):
        tags.append("regulatory")
    if any(x in blob for x in ("hack", "exploit", "breach", "outage")):
        tags.append("security_incident")
    return sorted(set(tags))


def _word_btc(blob: str) -> bool:
    return bool(re.search(r"\bbtc\b", blob))
