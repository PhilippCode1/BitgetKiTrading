from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
FE = ROOT / "services" / "feature-engine" / "src"
SHARED = ROOT / "shared" / "python" / "src"
for p in (FE, SHARED):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from feature_engine.worker import FeatureWorker  # noqa: E402
from shared_py.eventbus import EventEnvelope  # noqa: E402


def test_event_timestamp_age_uses_start_ts_ms_fallback() -> None:
    e = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        payload={
            "start_ts_ms": 1_000_000,
            "timeframe": "1m",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "usdt_vol": 1.0,
        },
    )
    age = FeatureWorker.event_timestamp_age_ms_at_ingress(e, 1_003_500)
    assert age == 3_500


def test_event_timestamp_age_prefers_exchange_ts() -> None:
    e = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        exchange_ts_ms=100,
        payload={
            "start_ts_ms": 5000,
            "timeframe": "1m",
            "open": 1,
            "high": 1,
            "low": 1,
            "close": 1,
            "usdt_vol": 1.0,
        },
    )
    age = FeatureWorker.event_timestamp_age_ms_at_ingress(e, 4000)
    assert age == 4000 - 100
