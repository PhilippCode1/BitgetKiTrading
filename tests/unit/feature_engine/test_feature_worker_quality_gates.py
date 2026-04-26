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

from feature_engine.worker import _validate_candle_close_event
from shared_py.eventbus import EventEnvelope


def test_feature_worker_quality_gate_flags_stale_and_broken_market_candle() -> None:
    now_ms = 1_700_000_000_000
    env = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        timeframe="5m",
        ingest_ts_ms=now_ms - 180_000,
        payload={
            "start_ts_ms": now_ms - 300_000,
            "open": 100_000,
            "high": 99_000,
            "low": 101_000,
            "close": -1,
            "base_vol": -2,
            "quote_vol": 10,
            "usdt_vol": 10,
        },
    )
    issues = _validate_candle_close_event(env, max_event_age_ms=120_000, now_ms=now_ms)
    assert "stale_market_event" in issues
    assert "close_invalid" in issues
    assert "high_below_body" in issues
    assert "low_above_body" in issues
    assert "base_vol_invalid" in issues
