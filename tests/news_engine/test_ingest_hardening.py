from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
NE_SRC = REPO / "services" / "news-engine" / "src"
SHARED_SRC = REPO / "shared" / "python" / "src"
for p in (NE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)


from news_engine.models import NewsCandidate
from news_engine.topic_tags import infer_topic_tags
from news_engine.url_normalization import canonical_news_url
from news_engine.worker import _ingest_time_skip_reason


def test_canonical_url_strips_utm_and_lowercases_host() -> None:
    raw = "HTTPS://WWW.Example.COM/path?utm_source=x&keep=1"
    c = canonical_news_url(raw)
    assert "utm_source" not in c
    assert "keep=1" in c
    assert c.startswith("https://example.com/")


def test_infer_topic_tags_detects_btc_and_macro() -> None:
    c = NewsCandidate(
        source="x",
        source_item_id=None,
        title="Bitcoin ETF decision expected",
        description="Fed rates in focus",
        content=None,
        url="https://a",
        author=None,
        language=None,
        published_ts_ms=None,
    )
    tags = infer_topic_tags(c)
    assert "btc" in tags
    assert "macro" in tags
    assert "regulatory" in tags


def test_ingest_time_skip_reason_stale_and_future(news_settings) -> None:
    s = news_settings
    now = 10_000_000_000
    assert _ingest_time_skip_reason(None, now_ms=now, settings=s) is None
    assert (
        _ingest_time_skip_reason(
            now - s.news_max_ingest_item_age_ms - 1,
            now_ms=now,
            settings=s,
        )
        == "stale"
    )
    assert (
        _ingest_time_skip_reason(
            now + s.news_max_future_skew_ms + 1,
            now_ms=now,
            settings=s,
        )
        == "future"
    )
