from __future__ import annotations

import logging
from typing import Any

from shared_py.eventbus import (
    EventEnvelope,
    RedisStreamBus,
    STREAM_NEWS_ITEM_CREATED,
    STREAM_NEWS_SCORED,
)

logger = logging.getLogger("news_engine.publisher")


def publish_news_item_created(
    bus: RedisStreamBus,
    *,
    news_id: str,
    row_id: int,
    source: str,
    url: str,
    title: str,
    published_ts_ms: int | None,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="news_item_created",
        symbol="GLOBAL",
        timeframe=None,
        exchange_ts_ms=published_ts_ms,
        dedupe_key=news_id,
        payload={
            "news_id": news_id,
            "id": row_id,
            "source": source,
            "url": url,
            "title": title,
        },
        trace=trace or {},
    )
    mid = bus.publish(STREAM_NEWS_ITEM_CREATED, env)
    logger.info("published news_item_created news_id=%s source=%s", news_id, source)
    return str(mid)


def publish_news_scored(
    bus: RedisStreamBus,
    *,
    news_id: str,
    relevance_score: int,
    sentiment: str,
    impact_window: str,
    published_ts_ms: int | None,
    trace: dict[str, Any] | None = None,
) -> str:
    env = EventEnvelope(
        event_type="news_scored",
        symbol="GLOBAL",
        timeframe=None,
        exchange_ts_ms=published_ts_ms,
        dedupe_key=f"{news_id}:{relevance_score}:{published_ts_ms or 0}",
        payload={
            "news_id": news_id,
            "relevance_score": relevance_score,
            "sentiment": sentiment,
            "impact_window": impact_window,
            "published_ts_ms": published_ts_ms,
        },
        trace=trace or {},
    )
    mid = bus.publish(STREAM_NEWS_SCORED, env)
    logger.info("published news_scored news_id=%s score=%s", news_id, relevance_score)
    return str(mid)
