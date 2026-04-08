from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = (
    Path(__file__).resolve().parents[2] / "services" / "structure-engine" / "src"
)
SERVICE_SRC_STR = str(SERVICE_SRC)
if SERVICE_SRC.is_dir() and SERVICE_SRC_STR not in sys.path:
    sys.path.insert(0, SERVICE_SRC_STR)

from structure_engine.algorithms.swings import Candle, detect_confirmed_swing
from structure_engine.algorithms.trend import structure_event_on_bar_edge


def _candle(ts: int, h: float, l: float, c: float | None = None) -> Candle:
    cc = c if c is not None else (h + l) / 2
    return Candle(ts_ms=ts, o=cc, h=h, l=l, c=cc)


def test_detect_confirmed_swing_high_with_defaults() -> None:
    candles = [
        _candle(0, 10, 9),
        _candle(1, 11, 9.5),
        _candle(2, 12, 10),  # pivot high at i=2, left_n=right_n=2
        _candle(3, 11, 10),
        _candle(4, 10.5, 10),
    ]
    swing = detect_confirmed_swing(candles, left_n=2, right_n=2)
    assert swing is not None
    assert swing.kind == "high"
    assert swing.ts_ms == 2
    assert swing.price == 12


def test_detect_confirmed_swing_not_confirmed_yet() -> None:
    candles = [
        _candle(0, 10, 9),
        _candle(1, 11, 9.5),
        _candle(2, 12, 10),
        _candle(3, 11, 10),
    ]
    assert detect_confirmed_swing(candles, 2, 2) is None


def test_structure_event_bos_up_only_on_edge() -> None:
    assert structure_event_on_bar_edge("UP", 105.0, 100.0, 102.0, 98.0) == ("BOS", "UP")
    assert structure_event_on_bar_edge("UP", 105.0, 104.0, 102.0, 98.0) == (None, None)


def test_structure_event_choch_down_on_edge() -> None:
    assert structure_event_on_bar_edge("UP", 97.0, 99.0, 102.0, 98.0) == ("CHOCH", "DOWN")
