from __future__ import annotations

from drawing_engine.settings import normalize_timeframe


def test_drawing_normalize_aliases() -> None:
    assert normalize_timeframe("4h") == "4H"
