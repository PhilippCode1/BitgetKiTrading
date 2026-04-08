from __future__ import annotations

import sys
from pathlib import Path

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "signal-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from signal_engine.models import ScoringContext
from signal_engine.scoring.structure_score import score_structure


def test_structure_up_boosts_score() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state={"trend_dir": "UP", "compression_flag": False},
        structure_events=[],
        primary_feature=None,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=100_000.0,
    )
    r = score_structure(ctx)
    assert r.score >= 55.0


def test_missing_structure_low() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature=None,
        features_by_tf={},
        drawings=[],
        news_row=None,
        last_close=None,
    )
    r = score_structure(ctx)
    assert r.score <= 30.0
    assert "structure_missing" in r.flags
