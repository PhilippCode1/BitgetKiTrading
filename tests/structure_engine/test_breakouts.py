from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = (
    Path(__file__).resolve().parents[2] / "services" / "structure-engine" / "src"
)
SERVICE_SRC_STR = str(SERVICE_SRC)
if SERVICE_SRC.is_dir() and SERVICE_SRC_STR not in sys.path:
    sys.path.insert(0, SERVICE_SRC_STR)

from structure_engine.algorithms.breakouts import (
    Box,
    build_box,
    prebreak_side,
    update_false_breakout_watch,
)


def test_build_box_window() -> None:
    highs = list(range(10, 30))
    lows = [h - 2 for h in highs]
    ts = list(range(1000, 1000 + len(highs)))
    box = build_box(highs, lows, ts, n_box=5)
    assert box is not None
    assert box.high == max(highs[-5:])
    assert box.low == min(lows[-5:])
    assert box.start_ts_ms == ts[-5]
    assert box.end_ts_ms == ts[-1]


def test_prebreak_side_near_high() -> None:
    box = Box(high=100.0, low=90.0, start_ts_ms=1, end_ts_ms=2)
    # knapp unter box_high, innerhalb weniger BPS
    assert prebreak_side(99.99, box, prebreak_bps=10.0) == "high"


def test_false_breakout_up_within_window() -> None:
    box = Box(high=100.0, low=99.0, start_ts_ms=1, end_ts_ms=2)
    pending, ev1 = update_false_breakout_watch(
        close=100.1,
        box=box,
        buffer_bps=1.0,
        window_bars=3,
        current_ts_ms=10,
        pending=None,
    )
    assert any(t == "BREAKOUT" for t, _ in ev1)
    assert pending is not None
    pending2, ev2 = update_false_breakout_watch(
        close=99.95,
        box=box,
        buffer_bps=1.0,
        window_bars=3,
        current_ts_ms=11,
        pending=pending,
    )
    assert any(
        t == "FALSE_BREAKOUT" and d.get("side") == "UP" for t, d in ev2
    )
    assert pending2 is None
