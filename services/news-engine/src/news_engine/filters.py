from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from news_engine.models import NewsCandidate


def parse_keyword_list(raw: str) -> list[str]:
    return [k.strip().lower() for k in raw.split(",") if k.strip()]


def text_matches_keywords(text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    blob = text.lower()
    return any(k in blob for k in keywords)


def candidate_matches_keywords(candidate: NewsCandidate, keywords: list[str]) -> bool:
    parts = [
        candidate.title or "",
        candidate.description or "",
        candidate.content or "",
    ]
    blob = " ".join(parts)
    return text_matches_keywords(blob, keywords)
