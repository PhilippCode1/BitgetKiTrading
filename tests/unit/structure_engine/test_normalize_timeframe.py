from __future__ import annotations

from structure_engine.settings import normalize_timeframe


def test_normalize_lowercase_hour() -> None:
    assert normalize_timeframe("1h") == "1H"


def test_normalize_passthrough_canonical() -> None:
    assert normalize_timeframe("1H") == "1H"
    assert normalize_timeframe("1m") == "1m"
