from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import Any

from shared_py.eventbus import RedisStreamBus
from shared_py.observability import touch_worker_heartbeat

from news_engine.config import NewsEngineSettings
from news_engine.events.publisher import publish_news_item_created
from news_engine.filters import candidate_matches_keywords
from news_engine.models import NewsCandidate
from news_engine.sources import (
    fetch_coindesk_rss,
    fetch_cryptopanic,
    fetch_gdelt_doc,
    fetch_newsapi_everything,
    fetch_newsapi_top,
)
from news_engine.storage.repo import NewsRepository, utc_now_ms
from news_engine.topic_tags import infer_topic_tags
from news_engine.url_normalization import canonical_news_url

_SOURCE_PRIORITY: dict[str, int] = {
    "cryptopanic": 0,
    "coindesk": 1,
    "newsapi": 2,
    "gdelt": 3,
}


def _source_rank(source: str) -> int:
    return _SOURCE_PRIORITY.get(source, 9)


def _prepare_candidate_for_storage(candidate: NewsCandidate) -> NewsCandidate:
    canon = canonical_news_url(candidate.url)
    tags = infer_topic_tags(candidate)
    frag = dict(candidate.raw_fragment)
    stripped = (candidate.url or "").strip()
    if canon != stripped:
        frag.setdefault("original_url", candidate.url)
    frag["topic_tags"] = tags
    return replace(candidate, url=canon, raw_fragment=frag)


def _ingest_time_skip_reason(
    published_ts_ms: int | None,
    *,
    now_ms: int,
    settings: NewsEngineSettings,
) -> str | None:
    if published_ts_ms is None:
        return None
    if published_ts_ms > now_ms + settings.news_max_future_skew_ms:
        return "future"
    if now_ms - published_ts_ms > settings.news_max_ingest_item_age_ms:
        return "stale"
    return None


class NewsIngestWorker:
    def __init__(
        self,
        settings: NewsEngineSettings,
        repo: NewsRepository,
        bus: RedisStreamBus,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._bus = bus
        self._logger = logger or logging.getLogger("news_engine.worker")
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._last_stats: dict[str, Any] = {}

    def stats_payload(self) -> dict[str, Any]:
        return dict(self._last_stats)

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def start_background(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="news-ingest-loop")

    async def _loop(self) -> None:
        interval = self._settings.news_poll_interval_sec
        while not self._stop.is_set():
            try:
                stats = await asyncio.to_thread(self.run_ingestion_once)
                self._last_stats = stats
                touch_worker_heartbeat("news_engine")
            except Exception as exc:  # pragma: no cover
                self._logger.exception("ingestion cycle failed: %s", exc)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except TimeoutError:
                continue

    def run_ingestion_once(self) -> dict[str, Any]:
        """Synchrone Ingestion (ein Durchlauf alle Quellen)."""
        settings = self._settings
        keywords = settings.keyword_list()
        collected: list[NewsCandidate] = []
        collected.extend(fetch_cryptopanic(settings))
        collected.extend(fetch_newsapi_top(settings))
        collected.extend(fetch_newsapi_everything(settings))
        collected.extend(fetch_coindesk_rss(settings))
        collected.extend(fetch_gdelt_doc(settings))

        collected.sort(
            key=lambda x: (
                _source_rank(x.source),
                -(x.published_ts_ms or 0),
            )
        )

        seen_urls: set[str] = set()
        now_ms = utc_now_ms()
        inserted = 0
        skipped_kw = 0
        skipped_dup = 0
        skipped_stale = 0
        skipped_future = 0

        for c in collected:
            prep = _prepare_candidate_for_storage(c)
            if prep.url in seen_urls:
                skipped_dup += 1
                continue
            seen_urls.add(prep.url)
            tskip = _ingest_time_skip_reason(
                prep.published_ts_ms, now_ms=now_ms, settings=settings
            )
            if tskip == "future":
                skipped_future += 1
                continue
            if tskip == "stale":
                skipped_stale += 1
                continue
            if not candidate_matches_keywords(prep, keywords):
                skipped_kw += 1
                continue
            row = self._repo.insert_candidate(prep, ingested_ts_ms=now_ms)
            if row is None:
                continue
            row_id, news_id = row
            publish_news_item_created(
                self._bus,
                news_id=news_id,
                row_id=row_id,
                source=prep.source,
                url=prep.url,
                title=prep.title,
                published_ts_ms=prep.published_ts_ms,
            )
            inserted += 1

        stats = {
            "ingest_collected": len(collected),
            "ingest_inserted": inserted,
            "ingest_skipped_keywords": skipped_kw,
            "ingest_skipped_duplicate_batch": skipped_dup,
            "ingest_skipped_stale": skipped_stale,
            "ingest_skipped_future_dated": skipped_future,
        }
        self._logger.info(
            "ingestion collected=%s inserted=%s skipped_kw=%s stale=%s future=%s",
            len(collected),
            inserted,
            skipped_kw,
            skipped_stale,
            skipped_future,
        )
        return stats
