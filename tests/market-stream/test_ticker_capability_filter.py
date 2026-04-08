from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MS_SRC = ROOT.parent / "services" / "market-stream" / "src"
if MS_SRC.is_dir() and str(MS_SRC) not in sys.path:
    sys.path.insert(0, str(MS_SRC))

from market_stream.collectors.ticker import _filter_ws_ticker_updates


def test_filter_ws_strips_futures_fields_on_spot() -> None:
    raw = {
        "last_pr": 1.0,
        "mark_price": 2.0,
        "funding_rate": 0.01,
        "holding_amount": 3.0,
    }
    out = _filter_ws_ticker_updates(
        raw,
        "spot",
        supports_funding=True,
        supports_open_interest=True,
    )
    assert "mark_price" not in out
    assert "funding_rate" not in out


def test_filter_ws_respects_funding_cap_on_futures() -> None:
    raw = {"funding_rate": 0.01, "holding_amount": 2.0, "mark_price": 1.0}
    out = _filter_ws_ticker_updates(
        raw,
        "futures",
        supports_funding=False,
        supports_open_interest=True,
    )
    assert "funding_rate" not in out
    assert out.get("holding_amount") == 2.0
