from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
if LEARNING_SRC.is_dir() and str(LEARNING_SRC) not in sys.path:
    sys.path.insert(0, str(LEARNING_SRC))

from learning_engine.labeling.target_windows import (
    clip_candles_to_evaluation_window,
    regime_target_stratification_hints,
)


def test_clip_keeps_only_window_and_flags_future_bar() -> None:
    candles = [
        {"start_ts_ms": 10},
        {"start_ts_ms": 50},
        {"start_ts_ms": 200},
    ]
    out, issues = clip_candles_to_evaluation_window(
        candles, decision_ts_ms=40, evaluation_end_ts_ms=100
    )
    assert [c["start_ts_ms"] for c in out] == [50]
    assert "candle_start_after_evaluation_end" in issues


def test_regime_hints_include_shock_note() -> None:
    h = regime_target_stratification_hints("shock")
    assert h["regime"] == "shock"
    assert any("Varianz" in n for n in h["notes"])


def test_regime_hints_dislocation_note() -> None:
    h = regime_target_stratification_hints("dislocation")
    assert h["regime"] == "dislocation"
    assert any("Spread" in n or "Funding" in n for n in h["notes"])
