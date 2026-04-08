from __future__ import annotations

import logging
from typing import Any

from shared_py.eventbus import RedisStreamBus

from news_engine.config import NewsEngineSettings
from news_engine.events.publisher import publish_news_scored
from news_engine.scoring.llm_enricher import (
    build_entities_json,
    fetch_llm_news_summary,
    merge_llm_with_rules,
)
from news_engine.scoring.rules_v1 import score_news
from news_engine.storage.repo import NewsRepository, utc_now_ms

logger = logging.getLogger("news_engine.scoring.runner")


def run_scoring_batch(
    settings: NewsEngineSettings,
    repo: NewsRepository,
    bus: RedisStreamBus,
    *,
    limit: int = 500,
) -> dict[str, Any]:
    version = settings.news_scoring_version
    rows = repo.fetch_pending_scoring(scoring_version=version, limit=limit)
    now_ms = utc_now_ms()
    done = 0
    llm_ok = 0
    llm_fail = 0

    for row in rows:
        row_id = int(row["id"])
        title = str(row.get("title") or "")
        description = row.get("description")
        content = row.get("content")
        text = f"{description or ''} {content or ''}"
        source = str(row.get("source") or "")
        url = str(row.get("url") or "")
        pub_ms = row.get("published_ts_ms")
        if pub_ms is not None:
            pub_ms = int(pub_ms)
        raw_json = row.get("raw_json")
        if not isinstance(raw_json, dict):
            raw_json = {}

        rule = score_news(
            title,
            text,
            source,
            pub_ms,
            raw_json=raw_json,
            now_ms=now_ms,
        )
        final = rule
        llm_blob: dict[str, Any] | None = None
        entities: list[Any] | None = None

        if settings.news_llm_enabled:
            llm = fetch_llm_news_summary(
                settings,
                title=title,
                description=str(description) if description else None,
                content=str(content) if content else None,
                url=url,
                source=source,
                published_ts_ms=pub_ms,
            )
            if llm:
                final, llm_blob = merge_llm_with_rules(
                    rule,
                    llm,
                    max_delta=settings.news_score_max_llm_delta,
                )
                entities = build_entities_json(llm)
                llm_ok += 1
            else:
                llm_fail += 1

        repo.update_scoring_row(
            row_id,
            relevance_score=final.relevance,
            sentiment=final.sentiment,
            impact_window=final.impact_window,
            scored_ts_ms=now_ms,
            scoring_version=version,
            llm_summary_json=llm_blob,
            entities_json=entities,
        )

        news_id = str(row.get("news_id") or "").strip()
        if settings.news_score_publish_events and news_id:
            try:
                publish_news_scored(
                    bus,
                    news_id=news_id,
                    relevance_score=final.relevance,
                    sentiment=final.sentiment,
                    impact_window=final.impact_window,
                    published_ts_ms=pub_ms,
                    trace={"scoring_version": version},
                )
            except Exception as exc:
                logger.warning("news_scored publish failed: %s", exc)

        done += 1

    return {
        "scored": done,
        "candidates": len(rows),
        "llm_enrich_ok": llm_ok,
        "llm_enrich_fail": llm_fail,
        "scoring_version": version,
    }
