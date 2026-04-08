from __future__ import annotations

from news_engine.filters import candidate_matches_keywords
from news_engine.sources import (
    fetch_coindesk_rss,
    fetch_cryptopanic,
    fetch_gdelt_doc,
    fetch_newsapi_everything,
    fetch_newsapi_top,
)


def test_fixture_sources_return_candidates(news_settings) -> None:
    s = news_settings
    all_rows = []
    all_rows.extend(fetch_cryptopanic(s))
    all_rows.extend(fetch_newsapi_top(s))
    all_rows.extend(fetch_newsapi_everything(s))
    all_rows.extend(fetch_coindesk_rss(s))
    all_rows.extend(fetch_gdelt_doc(s))
    assert len(all_rows) >= 4
    urls = {r.url for r in all_rows}
    # newsapi top + everything liefern in Fixture-Mode dieselbe Datei (bewusst)
    assert len(urls) >= 3
    assert len(urls) <= len(all_rows)


def test_keyword_filter_keeps_crypto_related(news_settings) -> None:
    s = news_settings
    kws = s.keyword_list()
    kept = 0
    for row in fetch_coindesk_rss(s):
        if candidate_matches_keywords(row, kws):
            kept += 1
    assert kept >= 1
