from __future__ import annotations

import time

import pytest
from news_engine.scoring.impact_window import resolve_impact_window
from news_engine.scoring.rules_v1 import score_news


def test_btc_and_coindesk_boost() -> None:
    now = 1_700_000_000_000
    s = score_news(
        "Bitcoin ETF approved",
        "SEC regulation update",
        "coindesk",
        now - 5 * 60 * 1000,
        raw_json={},
        now_ms=now,
    )
    assert s.relevance >= 60
    assert s.sentiment in ("bullisch", "mixed", "neutral")
    assert s.impact_window in ("sofort", "mittel", "langsam")


def test_bearish_hack() -> None:
    now = 1_700_000_000_000
    s = score_news(
        "Exchange hack",
        "Users report outflow issues",
        "cryptopanic",
        now - 120_000,
        raw_json={},
        now_ms=now,
    )
    assert s.sentiment in ("baerisch", "mixed")


def test_newsapi_top_headlines_impact_immediate() -> None:
    iw = resolve_impact_window(
        title="Market",
        text="update",
        source="newsapi",
        raw_json={"ingest_channel": "top_headlines"},
        age_minutes=5,
    )
    assert iw == "sofort"


def test_topic_tags_in_raw_json_boost_score() -> None:
    now = 1_700_000_000_000
    base = score_news(
        "Generic headline",
        "market text",
        "gdelt",
        now - 60_000,
        raw_json={},
        now_ms=now,
    )
    tagged = score_news(
        "Generic headline",
        "market text",
        "gdelt",
        now - 60_000,
        raw_json={"topic_tags": ["btc", "macro"]},
        now_ms=now,
    )
    assert tagged.relevance >= base.relevance


def test_age_multiplier_reduces_score() -> None:
    base_ts = 1_700_000_000_000
    young = score_news("bitcoin rally", "btc", "gdelt", base_ts - 60_000, now_ms=base_ts)
    old = score_news("bitcoin rally", "btc", "gdelt", base_ts - 10 * 3600_000, now_ms=base_ts)
    assert young.relevance >= old.relevance


def test_fixture_mode_stable_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)
    s = score_news("x", "crypto market", "newsapi", 1_699_999_000_000)
    assert 0 <= s.relevance <= 100
