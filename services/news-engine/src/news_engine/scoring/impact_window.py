"""
Heuristiken fuer impact_window (deutsch: sofort | mittel | langsam).

Deterministisch, dokumentiert in docs/news_scoring.md.
"""

from __future__ import annotations

from typing import Any


def resolve_impact_window(
    *,
    title: str,
    text: str,
    source: str,
    raw_json: dict[str, Any] | None,
    age_minutes: float,
) -> str:
    t = f"{title} {text}".lower()
    raw = raw_json or {}
    fragment = raw.get("fragment") if isinstance(raw.get("fragment"), dict) else {}
    channel = raw.get("ingest_channel") or fragment.get("ingest_channel")

    def has(*kw: str) -> bool:
        return any(k in t for k in kw)

    # Breaking / Top-Headlines (NewsAPI) -> sofort
    if source == "newsapi" and channel == "top_headlines":
        return "sofort"
    if age_minutes < 30 and has("breaking", "urgent", "flash"):
        return "sofort"

    macro_slow = has(
        "outlook",
        "analysis",
        "opinion",
        "commentary",
        "weekly",
        "monthly",
        "long term",
        "langfristig",
    )
    regulation = has("fed", "etf", "sec", "regulation", "cpi", "inflation", "rates")

    if regulation and not macro_slow:
        return "sofort" if has("breaking", "sec", "lawsuit", "ban", "hack") else "mittel"
    if macro_slow:
        return "langsam" if not regulation else "mittel"
    return "mittel"
