"""Gemeinsame Feature-Extraktion fuer AMS-Stress und Export zum Risk-Governor."""

from __future__ import annotations

from typing import Any

import numpy as np


def toxicity_feature_dim() -> int:
    return 6


def features_from_ams_moments(moments: dict[str, Any], toxicity: float) -> np.ndarray:
    lr = moments.get("log_return") or {}
    di = moments.get("depth_imbalance") or {}
    corr = float(moments.get("price_depth_corr") or 0.0)
    return np.array(
        [
            float(toxicity),
            float(lr.get("skewness") or 0.0),
            float(lr.get("kurtosis_excess") or 0.0),
            float(di.get("skewness") or 0.0),
            float(di.get("kurtosis_excess") or 0.0),
            corr,
        ],
        dtype=np.float64,
    )


def features_from_signal_row_fallback(signal_row: dict[str, Any]) -> np.ndarray:
    """Live-Fallback (ohne AMS-Momente): skalierte Signal-Scores als Proxy."""
    def _n(key: str) -> float:
        try:
            return float(signal_row.get(key) or 0.0) / 100.0
        except (TypeError, ValueError):
            return 0.0

    return np.array(
        [
            _n("risk_score_0_100"),
            _n("structure_score_0_100"),
            _n("momentum_score_0_100"),
            _n("news_score_0_100"),
            float(signal_row.get("uncertainty_effective_for_leverage_0_1") or 0.0),
            float(signal_row.get("probability_0_1") or 0.0),
        ],
        dtype=np.float64,
    )
