from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared_py.observability import touch_worker_heartbeat

from news_engine.config import NewsEngineSettings
from news_engine.social.aggregator import SentimentAggregator
from news_engine.social.embedding_client import embed_texts
from news_engine.social.pipeline import SocialSentimentPipeline
from news_engine.social.reference import load_reference_bundle
from news_engine.social.telegram_stream_adapter import TelegramStreamAdapter
from news_engine.social.types import SocialIncomingMessage
from news_engine.social.x_stream_adapter import XStreamAdapter

logger = logging.getLogger("news_engine.social.worker")


class SocialStreamWorker:
    """Startet X-/Telegram-Producer und verarbeitet Queue (Embeddings + Eventbus)."""

    def __init__(
        self,
        settings: NewsEngineSettings,
        bus: Any,
        *,
        logger_: logging.Logger | None = None,
    ) -> None:
        self._settings = settings
        self._bus = bus
        self._logger = logger_ or logger
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._queue: asyncio.Queue[SocialIncomingMessage] = asyncio.Queue(maxsize=2000)
        self._pipeline: SocialSentimentPipeline | None = None
        self._stats: dict[str, Any] = {
            "social_pipeline_enabled": False,
            "social_messages_processed": 0,
            "social_last_error": None,
        }

    def stats_payload(self) -> dict[str, Any]:
        return dict(self._stats)

    async def start_background(self) -> None:
        if not self._settings.social_pipeline_enabled:
            self._logger.info("SocialStreamWorker: deaktiviert (SOCIAL_PIPELINE_ENABLED=false)")
            return
        self._stats["social_pipeline_enabled"] = True
        self._tasks.append(asyncio.create_task(self._bootstrap_and_run(), name="social-pipeline"))

    async def stop(self) -> None:
        self._stop.set()
        for t in self._tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def _bootstrap_and_run(self) -> None:
        redis = getattr(self._bus, "redis", None)
        try:
            ref = load_reference_bundle(self._settings.social_reference_json_path or "")
            panic = list(ref.get("panic_texts_en") or [])
            euph = list(ref.get("euphoria_texts_en") or [])
            if not panic or not euph:
                raise ValueError("Referenz-JSON braucht panic_texts_en und euphoria_texts_en")
            all_t = panic + euph
            vecs, _, _ = await embed_texts(
                base_url=self._settings.social_inference_base_url,
                texts=all_t,
                redis=redis,
                cache_ttl_sec=self._settings.social_embed_cache_ttl_sec,
            )
            if any(v is None for v in vecs):
                raise RuntimeError("Referenz-Embeddings unvollstaendig (inference-server pruefen)")
            n_p = len(panic)
            panic_vecs = [vecs[i] for i in range(n_p)]
            euph_vecs = [vecs[i] for i in range(n_p, len(vecs))]
            agg = SentimentAggregator.from_reference_vectors(
                panic_vecs,
                euph_vecs,
                roll_alpha=self._settings.social_roll_alpha,
            )
            self._pipeline = SocialSentimentPipeline(self._settings, self._bus, redis, agg)
        except Exception as exc:
            self._logger.exception("SocialStreamWorker: Bootstrap fehlgeschlagen: %s", exc)
            self._stats["social_last_error"] = str(exc)[:500]
            return

        if self._settings.social_x_enabled and (self._settings.twitter_bearer_token or "").strip():
            x = XStreamAdapter(
                bearer_token=self._settings.twitter_bearer_token or "",
                rule_value=self._settings.social_x_rule_value,
                replace_rules_on_start=self._settings.social_x_replace_rules_on_start,
            )
            self._tasks.append(asyncio.create_task(x.run(self._queue, self._stop), name="social-x-stream"))
        elif self._settings.social_x_enabled:
            self._logger.warning("SOCIAL_X_ENABLED ohne TWITTER_BEARER_TOKEN — X-Stream aus")

        if self._settings.social_telegram_enabled:
            tid = self._settings.telegram_api_id
            th = (self._settings.telegram_api_hash or "").strip()
            ts = (self._settings.telegram_session_string or "").strip()
            chans = [c.strip() for c in self._settings.telegram_alpha_channels.split(",") if c.strip()]
            if tid and th and ts and chans:
                tg = TelegramStreamAdapter(
                    api_id=int(tid),
                    api_hash=th,
                    session_string=ts,
                    channel_specs=chans,
                )
                self._tasks.append(
                    asyncio.create_task(tg.run(self._queue, self._stop), name="social-telegram-stream")
                )
            else:
                self._logger.warning(
                    "SOCIAL_TELEGRAM_ENABLED aber API_ID/HASH/SESSION/Kanaele unvollstaendig — Telegram aus"
                )

        self._tasks.append(asyncio.create_task(self._consume_loop(), name="social-consume"))

    async def _consume_loop(self) -> None:
        assert self._pipeline is not None
        while not self._stop.is_set():
            try:
                msg = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                await self._pipeline.handle(msg)
                self._stats["social_messages_processed"] = (
                    int(self._stats["social_messages_processed"]) + 1
                )
                touch_worker_heartbeat("news_engine_social")
            except Exception as exc:
                self._logger.exception("Social consume: %s", exc)
                self._stats["social_last_error"] = str(exc)[:500]
