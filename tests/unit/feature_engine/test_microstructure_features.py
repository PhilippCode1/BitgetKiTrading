from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FEATURE_SRC = ROOT / "services" / "feature-engine" / "src"
SHARED_SRC = ROOT / "shared" / "python" / "src"
for candidate in (FEATURE_SRC, SHARED_SRC):
    candidate_str = str(candidate)
    if candidate.is_dir() and candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from feature_engine.features.microstructure import build_market_context_features
from feature_engine.storage import (
    FundingSnapshot,
    OpenInterestSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)


def test_market_context_features_from_orderbook_funding_and_oi() -> None:
    features = build_market_context_features(
        market_family="futures",
        orderbook=OrderBookSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_000_000,
            bids=[(100_000.0, 1.0), (99_990.0, 2.0)],
            asks=[(100_010.0, 1.2), (100_020.0, 2.2)],
        ),
        ticker=None,
        funding=FundingSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_000_000,
            source="bitget_rest_funding",
            funding_rate=0.0002,
            interval_hours=8,
            next_update_ms=1_700_028_800_000,
        ),
        open_interest=OpenInterestSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_000_000,
            source="bitget_rest_open_interest",
            size=120_000.0,
        ),
        previous_open_interest=OpenInterestSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_699_999_700_000,
            source="bitget_rest_open_interest",
            size=100_000.0,
        ),
        candle_usdt_vol=150_000.0,
        timeframe_ms=300_000,
        analysis_ts_ms=1_700_000_005_000,
        atrp_14=0.2,
    )
    assert features.liquidity_source == "orderbook_levels"
    assert features.spread_bps is not None and features.spread_bps > 0
    assert features.execution_cost_bps is not None and features.execution_cost_bps > features.spread_bps
    assert features.impact_buy_bps_5000 is not None
    assert features.funding_rate_bps == 2.0
    assert features.funding_cost_bps_window is not None and features.funding_cost_bps_window > 0
    assert features.open_interest == 120_000.0
    assert features.open_interest_change_pct == 20.0
    assert features.funding_time_to_next_ms == 28_795_000
    assert features.orderbook_age_ms == 5_000


def test_market_context_features_fall_back_to_ticker_without_slippage_masking() -> None:
    features = build_market_context_features(
        market_family="spot",
        orderbook=None,
        ticker=TickerSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_010_000,
            source="bitget_ws_ticker",
            bid_pr=100_000.0,
            ask_pr=100_012.0,
            bid_sz=0.5,
            ask_sz=0.4,
            last_pr=100_005.0,
            mark_price=100_004.0,
            index_price=100_003.0,
        ),
        funding=None,
        open_interest=None,
        previous_open_interest=None,
        candle_usdt_vol=90_000.0,
        timeframe_ms=60_000,
        analysis_ts_ms=1_700_000_012_000,
        atrp_14=0.1,
    )
    assert features.liquidity_source == "ticker:bitget_ws_ticker"
    assert features.spread_bps is not None and features.spread_bps > 0
    assert features.execution_cost_bps == features.spread_bps
    assert features.impact_buy_bps_5000 is None
    assert features.funding_source == "not_applicable"
    assert features.open_interest_source == "not_applicable"
    assert features.mark_index_spread_bps is None


def test_futures_without_open_interest_capability_skips_oi_metrics() -> None:
    features = build_market_context_features(
        market_family="futures",
        orderbook=None,
        ticker=TickerSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_010_000,
            source="bitget_ws_ticker",
            bid_pr=100_000.0,
            ask_pr=100_012.0,
            bid_sz=0.5,
            ask_sz=0.4,
            last_pr=100_005.0,
            mark_price=100_004.0,
            index_price=100_003.0,
        ),
        funding=FundingSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_000_000,
            source="f",
            funding_rate=0.0001,
            interval_hours=8,
            next_update_ms=1_700_010_000_000,
        ),
        open_interest=OpenInterestSnapshot(
            symbol="BTCUSDT",
            ts_ms=1_700_000_000_000,
            source="oi",
            size=50_000.0,
        ),
        previous_open_interest=None,
        candle_usdt_vol=90_000.0,
        timeframe_ms=60_000,
        analysis_ts_ms=1_700_000_012_000,
        atrp_14=0.1,
        supports_funding=True,
        supports_open_interest=False,
    )
    assert features.open_interest is None
    assert features.open_interest_source == "not_applicable"
