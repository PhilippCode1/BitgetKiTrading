from __future__ import annotations

import asyncio
import time
from typing import Any
import pytest

from news_engine.config import NewsEngineSettings
from news_engine.social.aggregator import SentimentAggregator, infer_symbols
from news_engine.social.pipeline import SocialSentimentPipeline
from news_engine.social.types import SocialIncomingMessage


def test_infer_symbols_etf_approved() -> None:
    assert "BTCUSDT" in infer_symbols("ETF approved!")


def _uv1024(a: float, b: float) -> list[float]:
    v = [0.0] * 1024
    v[0] = a
    v[1] = b
    return v


def test_social_pipeline_etf_positive_and_fast(monkeypatch: pytest.MonkeyPatch, news_settings: Any) -> None:
    monkeypatch.setenv("SOCIAL_SPAM_MIN_FOLLOWERS", "0")
    settings = NewsEngineSettings()
    panic = _uv1024(1.0, 0.0)
    euph = _uv1024(0.0, 1.0)
    agg = SentimentAggregator(panic_centroid=panic, euphoria_centroid=euph, roll_alpha=0.4)

    published: list[tuple[str, Any]] = []

    class _Bus:
        def publish(self, stream: str, env: Any) -> None:
            published.append((stream, env))

    async def _fake_embed(**kwargs: Any) -> tuple[list[list[float] | None], str, float]:
        return [_uv1024(0.0, 1.0)], "mock", 0.25

    monkeypatch.setattr("news_engine.social.pipeline.embed_texts", _fake_embed)

    pipe = SocialSentimentPipeline(settings, _Bus(), None, agg)
    t0 = time.perf_counter()
    wall = asyncio.run(
        pipe.handle(
            SocialIncomingMessage(
                source="x",
                text="ETF approved!",
                author_id="u1",
                external_id="tw-1",
                followers=50_000,
            )
        )
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert wall is not None
    assert elapsed_ms < 500.0
    assert published
    stream, env = published[0]
    assert "social_sentiment" in stream
    pl = env.payload
    assert pl.get("event_name") == "SOCIAL_SENTIMENT_UPDATE"
    assert float(pl.get("sentiment_score") or 0.0) > 0.2


def test_social_worker_bootstrap_embed_order(monkeypatch: pytest.MonkeyPatch, news_settings: Any) -> None:
    """Referenz-Batch: panic- und Euphorie-Vektoren werden getrennt ausgewertet."""
    from news_engine.social.worker import SocialStreamWorker

    monkeypatch.setenv("SOCIAL_PIPELINE_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_SPAM_MIN_FOLLOWERS", "0")
    settings = NewsEngineSettings()

    calls: list[int] = []

    async def _fake_embed(*, texts: list[str], **kwargs: Any) -> tuple[list[list[float] | None], str, float]:
        calls.append(len(texts))
        out: list[list[float]] = []
        for _t in texts:
            if len(calls) == 1 and len(texts) >= 5:
                out.append(_uv1024(1.0, 0.0))
            else:
                out.append(_uv1024(0.0, 1.0))
        return out, "mock", 1.0

    monkeypatch.setattr("news_engine.social.worker.embed_texts", _fake_embed)

    class _Bus:
        redis = None

        def publish(self, *args: Any, **kwargs: Any) -> None:
            pass

    w = SocialStreamWorker(settings, _Bus())

    async def _run() -> None:
        await w.start_background()
        await asyncio.sleep(0.05)
        await w.stop()

    asyncio.run(_run())
    assert calls and calls[0] >= 5
