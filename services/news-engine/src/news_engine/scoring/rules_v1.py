"""
Regelbasierter News-Score V1 — deterministisch.

Siehe docs/news_scoring.md.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from news_engine.scoring.impact_window import resolve_impact_window


@dataclass(frozen=True)
class Scored:
    relevance: int
    sentiment: str
    impact_window: str


def _has(t: str, *kw: str) -> bool:
    return any(k in t for k in kw)


def _btc_hit(t: str) -> bool:
    if "bitcoin" in t:
        return True
    return bool(re.search(r"\bbtc\b", t))


def _minor_noise_bonus(t: str) -> int:
    """Kleiner Zuschlag 0–10 fuer allgemeinen Crypto-/Markt-Kontext ohne Top-Keywords."""
    if len(t.strip()) < 12:
        return 0
    peripheral = (
        "crypto",
        "blockchain",
        "digital asset",
        "token",
        "defi",
        "exchange",
        "trading",
        "market",
        "coin",
    )
    hits = sum(1 for p in peripheral if p in t)
    if hits == 0:
        return 0
    return min(10, 4 + hits * 2)


def score_news(
    title: str,
    text: str,
    source: str,
    published_ts_ms: int | None,
    *,
    raw_json: dict[str, Any] | None = None,
    now_ms: int | None = None,
) -> Scored:
    title = title or ""
    text = text or ""
    t = f"{title} {text}".lower()
    score = 0

    if _btc_hit(t):
        score += 30
    if _has(t, "etf", "sec", "regulation"):
        score += 25
    if _has(t, "lawsuit"):
        score += 25
    if _has(t, "fed", "cpi", "inflation", "rates"):
        score += 20
    if _has(t, "hack", "exploit", "breach"):
        score += 25

    score += _minor_noise_bonus(t)

    if raw_json and isinstance(raw_json.get("topic_tags"), list):
        tagset = {str(x).lower() for x in raw_json["topic_tags"]}
        if "btc" in tagset:
            score += 4
        if "macro" in tagset:
            score += 3
        if "regulatory" in tagset:
            score += 3
        if "security_incident" in tagset:
            score += 5
        if "eth_defi" in tagset:
            score += 2

    src_bonus = {"cryptopanic": 10, "coindesk": 10, "newsapi": 5, "gdelt": 5}.get(source, 0)
    score += src_bonus

    clock = now_ms if now_ms is not None else int(time.time() * 1000)
    pub = published_ts_ms if published_ts_ms is not None else clock
    age_min = max(0.0, (clock - pub) / 60000.0)
    if age_min < 10:
        mult = 1.2
    elif age_min < 60:
        mult = 1.0
    elif age_min < 360:
        mult = 0.8
    else:
        mult = 0.5

    score = int(min(100, max(0, round(score * mult))))

    bull = _has(t, "approval", "adopt", "inflow", "surge", "rally")
    bear = _has(t, "ban", "lawsuit", "hack", "outflow", "crash", "selloff", "exploit")
    if bull and bear:
        sentiment = "mixed"
    elif bull:
        sentiment = "bullisch"
    elif bear:
        sentiment = "baerisch"
    else:
        sentiment = "neutral"

    impact = resolve_impact_window(
        title=title,
        text=text,
        source=source,
        raw_json=raw_json,
        age_minutes=age_min,
    )

    return Scored(relevance=score, sentiment=sentiment, impact_window=impact)
