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
from signal_engine.scoring.multi_timeframe_score import score_multi_timeframe


def _row(td: int) -> dict:
    return {"trend_dir": td}


def test_mtf_aligned_high() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature=None,
        features_by_tf={
            "1m": _row(1),
            "5m": _row(1),
            "15m": _row(1),
            "1H": _row(1),
            "4H": _row(1),
        },
        drawings=[],
        news_row=None,
        last_close=None,
    )
    r = score_multi_timeframe(ctx, primary_structure_sign=1)
    assert r.score >= 85.0


def test_mtf_conflict_low() -> None:
    ctx = ScoringContext(
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=1,
        structure_state=None,
        structure_events=[],
        primary_feature=None,
        features_by_tf={
            "1m": _row(1),
            "5m": _row(1),
            "15m": _row(1),
            "1H": _row(-1),
            "4H": _row(-1),
        },
        drawings=[],
        news_row=None,
        last_close=None,
    )
    r = score_multi_timeframe(ctx, primary_structure_sign=1)
    assert r.score < 55.0
