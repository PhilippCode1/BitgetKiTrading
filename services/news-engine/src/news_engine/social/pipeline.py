from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from news_engine.config import NewsEngineSettings
from news_engine.social.aggregator import SentimentAggregator, infer_symbols
from news_engine.social.embedding_client import embed_texts
from news_engine.social.publisher import publish_social_sentiment_update
from news_engine.social.spam_filter import allow_social_message

logger = logging.getLogger("news_engine.social.pipeline")


class SocialSentimentPipeline:
    def __init__(
        self,
        settings: NewsEngineSettings,
        bus: Any,
        redis: Any | None,
        aggregator: SentimentAggregator,
    ) -> None:
        self._settings = settings
        self._bus = bus
        self._redis = redis
        self._agg = aggregator

    async def handle(self, msg: Any) -> float | None:
        """Verarbeitet eine Nachricht; gibt Gesamt-Wandzeit ms zurueck (None bei Skip)."""
        t_wall0 = time.perf_counter()
        if not allow_social_message(
            author_id=msg.author_id,
            followers=msg.followers,
            redis=self._redis,
            min_followers=self._settings.social_spam_min_followers,
            max_posts_per_window=self._settings.social_spam_max_posts_per_window,
            window_sec=self._settings.social_spam_window_sec,
            reject_missing_followers=self._settings.social_spam_reject_missing_followers,
        ):
            return None
        vecs, backend, emb_ms = await embed_texts(
            base_url=self._settings.social_inference_base_url,
            texts=[msg.text],
            redis=self._redis,
            cache_ttl_sec=self._settings.social_embed_cache_ttl_sec,
        )
        emb = vecs[0] if vecs else None
        if emb is None:
            logger.warning("social embed fehlgeschlagen source=%s id=%s", msg.source, msg.external_id)
            return None
        inst, cp, ce = self._agg.instantaneous_score(emb)
        symbols = infer_symbols(msg.text)
        excerpt = (msg.text or "")[:500]
        for sym in symbols:
            roll = self._agg.update_rolling(self._redis, sym, inst)
            dk = hashlib.sha256(f"{msg.source}:{msg.external_id}:{sym}".encode("utf-8")).hexdigest()
            publish_social_sentiment_update(
                self._bus,
                symbol=sym,
                sentiment_score=inst,
                rolling_score=roll,
                panic_cosine=cp,
                euphoria_cosine=ce,
                source=msg.source,
                text_excerpt=excerpt,
                embed_backend=backend,
                embed_wall_ms=emb_ms,
                dedupe_key=dk,
            )
        total_ms = (time.perf_counter() - t_wall0) * 1000.0
        logger.debug("social handled src=%s sym=%s total_ms=%.1f", msg.source, symbols, total_ms)
        return total_ms
