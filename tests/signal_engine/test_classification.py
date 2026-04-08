from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.scoring.classification import classify_signal


def test_rejected_is_warnung(signal_settings) -> None:
    c = classify_signal(
        signal_settings,
        composite_strength=80.0,
        decision_state="rejected",
        layer_flags=[],
        multi_tf_score=70.0,
        risk_score=70.0,
    )
    assert c == "warnung"


def test_gross_requires_high_bar(signal_settings) -> None:
    c = classify_signal(
        signal_settings,
        composite_strength=85.0,
        decision_state="accepted",
        layer_flags=[],
        multi_tf_score=65.0,
        risk_score=60.0,
    )
    assert c == "gross"


def test_false_breakout_warnung(signal_settings) -> None:
    c = classify_signal(
        signal_settings,
        composite_strength=70.0,
        decision_state="accepted",
        layer_flags=["recent_false_breakout"],
        multi_tf_score=70.0,
        risk_score=70.0,
    )
    assert c == "warnung"
