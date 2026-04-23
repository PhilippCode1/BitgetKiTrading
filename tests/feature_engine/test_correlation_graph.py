from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SERVICE_SRC = Path(__file__).resolve().parents[2] / "services" / "feature-engine" / "src"
SHARED_SRC = Path(__file__).resolve().parents[2] / "shared" / "python" / "src"
for p in (SERVICE_SRC, SHARED_SRC):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from feature_engine.correlation_graph import (  # noqa: E402
    _shrink_correlation,
    _spillover_scores,
    detect_regime_divergence,
)


def test_detect_regime_divergence_synthetic() -> None:
    idx = pd.date_range("2024-01-01", periods=12, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "UUP": [0.007] * 12,
            "BTC": [0.0001] * 12,
        },
        index=idx,
    )
    trig, score, _dbg = detect_regime_divergence(df)
    assert trig is True
    assert score > 0.0


def test_spillover_numpy_fallback() -> None:
    n = 3
    c = np.eye(n, dtype=np.float64) * 0.9 + 0.1
    c = _shrink_correlation(c, eps=0.1)
    imp = np.array([0.5, -0.2, 0.1], dtype=np.float64)
    out = _spillover_scores(c, imp)
    assert len(out) == n
    assert all(isinstance(x, float) for x in out)
