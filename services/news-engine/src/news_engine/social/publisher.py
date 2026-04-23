from __future__ import annotations

import logging
import time
from typing import Any

from shared_py.eventbus.envelope import STREAM_SOCIAL_SENTIMENT_UPDATE, EventEnvelope

logger = logging.getLogger("news_engine.social.publisher")


def publish_social_sentiment_update(
    bus: Any,
    *,
    symbol: str,
    sentiment_score: float,
    rolling_score: float,
    panic_cosine: float,
    euphoria_cosine: float,
    source: str,
    text_excerpt: str,
    embed_backend: str,
    embed_wall_ms: float,
    dedupe_key: str,
) -> None:
    ts = int(time.time() * 1000)
    excerpt = (text_excerpt or "").strip().replace("\n", " ")[:400]
    env = EventEnvelope(
        event_type="social_sentiment_update",
        symbol=symbol.upper(),
        dedupe_key=dedupe_key,
        payload={
            "event_name": "SOCIAL_SENTIMENT_UPDATE",
            "symbol": symbol.upper(),
            "sentiment_score": round(float(sentiment_score), 6),
            "rolling_sentiment_score": round(float(rolling_score), 6),
            "panic_cosine": round(float(panic_cosine), 6),
            "euphoria_cosine": round(float(euphoria_cosine), 6),
            "source": source,
            "text_excerpt": excerpt,
            "embedding_backend": embed_backend,
            "embed_wall_ms": round(float(embed_wall_ms), 3),
            "timestamp_ms": ts,
        },
        trace={"source": "news-engine-social"},
    )
    bus.publish(STREAM_SOCIAL_SENTIMENT_UPDATE, env)
    logger.info(
        "SOCIAL_SENTIMENT_UPDATE sym=%s inst=%.3f roll=%.3f src=%s embed_ms=%.1f",
        symbol,
        sentiment_score,
        rolling_score,
        source,
        embed_wall_ms,
    )
