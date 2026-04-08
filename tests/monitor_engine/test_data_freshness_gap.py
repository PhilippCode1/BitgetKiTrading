from __future__ import annotations

from monitor_engine.checks.data_freshness import classify_age, detect_gap_count


def test_detect_gap_count_none_for_short_series() -> None:
    assert detect_gap_count([1000, 2000], 60_000) == 0


def test_detect_gap_count_finds_jump() -> None:
    # 1m Kerzen: erwartet 60000ms, Sprung 0 -> 200000 = Luecke
    ts = [400_000, 200_000, 0]
    assert detect_gap_count(ts, 60_000) >= 1


def test_classify_age() -> None:
    assert classify_age(None, 1000) == "critical"
    assert classify_age(50, 1000) == "ok"
    assert classify_age(800, 1000) == "warn"
    assert classify_age(1200, 1000) == "critical"
