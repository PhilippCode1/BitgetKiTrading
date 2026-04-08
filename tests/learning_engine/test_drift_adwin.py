from __future__ import annotations

from learning_engine.drift.adwin_detector import SimpleAdwin, run_adwin_on_series


def test_adwin_detects_mean_shift() -> None:
    adwin = SimpleAdwin(delta=0.05, min_window=10, max_window=100)
    fired = False
    first_half = [1.0] * 15
    second_half = [-1.0] * 15
    prev = False
    for v in first_half + second_half:
        d = adwin.update(v)
        if d and not prev:
            fired = True
        prev = d
    assert fired, "erwartet Drift nach Mittelwertwechsel"


def test_run_adwin_on_series_indices() -> None:
    vals = [0.01] * 25 + [5.0] * 25
    hits = run_adwin_on_series(vals, delta=0.5, min_window=10, max_window=200)
    assert len(hits) >= 1
