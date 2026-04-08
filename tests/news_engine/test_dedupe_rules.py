from __future__ import annotations

from news_engine.filters import (
    candidate_matches_keywords,
    parse_keyword_list,
    text_matches_keywords,
)
from news_engine.models import NewsCandidate


def test_parse_keywords() -> None:
    assert parse_keyword_list("bitcoin, BTC ,etf") == ["bitcoin", "btc", "etf"]


def test_text_matches() -> None:
    assert text_matches_keywords("The SEC and Bitcoin", ["sec", "bitcoin"])
    assert not text_matches_keywords("only weather", ["btc"])


def test_candidate_match() -> None:
    c = NewsCandidate(
        source="coindesk",
        source_item_id="1",
        title="ETF flows",
        description="btcusdt pair",
        content=None,
        url="https://www.coindesk.com/x",
        author=None,
        language=None,
        published_ts_ms=1,
        raw_fragment={},
    )
    assert candidate_matches_keywords(c, ["etf", "btcusdt"])


def test_batch_url_dedupe_logic() -> None:
    a = NewsCandidate(
        source="x",
        source_item_id=None,
        title="t",
        description=None,
        content=None,
        url="https://a/1",
        author=None,
        language=None,
        published_ts_ms=None,
        raw_fragment={},
    )
    b = NewsCandidate(
        source="y",
        source_item_id=None,
        title="t2",
        description=None,
        content=None,
        url="https://a/1",
        author=None,
        language=None,
        published_ts_ms=None,
        raw_fragment={},
    )
    seen: set[str] = set()
    uniq = []
    for c in (a, b):
        if c.url in seen:
            continue
        seen.add(c.url)
        uniq.append(c)
    assert len(uniq) == 1
