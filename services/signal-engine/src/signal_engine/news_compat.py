"""
Kompatibilitaet: app.news_items.sentiment ist Text (Prompt 17), Signal-Engine nutzt Float.
"""

from __future__ import annotations

from typing import Any


def news_sentiment_as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().lower()
    mapping = {
        "bullisch": 0.5,
        "bullish": 0.5,
        "baerisch": -0.5,
        "bärisch": -0.5,
        "bearish": -0.5,
        "neutral": 0.0,
        "mixed": 0.0,
        "unknown": 0.0,
    }
    if s in mapping:
        return mapping[s]
    return 0.0
