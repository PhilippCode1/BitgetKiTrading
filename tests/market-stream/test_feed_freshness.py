from __future__ import annotations

from market_stream.feed_health import compute_quote_age_ms, gapfill_triggers_orderbook_resync


def test_compute_quote_age_ms() -> None:
    now = 1_000_000
    at, ao = compute_quote_age_ms(
        now_ms=now,
        last_quote_ts_ms=now - 5000,
        last_orderbook_ts_ms=now - 10_000,
    )
    assert at == 5000
    assert ao == 10_000


def test_gapfill_triggers_orderbook_resync() -> None:
    assert gapfill_triggers_orderbook_resync("reconnect") is True
    assert gapfill_triggers_orderbook_resync("stale-data") is True
    assert gapfill_triggers_orderbook_resync("seq-gap-x-1-2") is True
    assert gapfill_triggers_orderbook_resync("other") is False
