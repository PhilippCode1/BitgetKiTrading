"""6-dim Feature-Vektor (kompatibel mit AMS-Trainingspfad der learning-engine)."""

from __future__ import annotations

from typing import Any

import numpy as np


def feature_vector_from_context(context: dict[str, Any]) -> np.ndarray | None:
    raw = context.get("ams_toxicity_feature_vector")
    if isinstance(raw, (list, tuple)) and len(raw) == 6:
        try:
            return np.asarray([float(x) for x in raw], dtype=np.float64).reshape(1, -1)
        except (TypeError, ValueError):
            return None
    ams = context.get("ams_last_moments")
    tox = context.get("ams_last_toxicity_0_1")
    if isinstance(ams, dict) and tox is not None:
        try:
            t = float(tox)
        except (TypeError, ValueError):
            return None
        lr = ams.get("log_return") or {}
        di = ams.get("depth_imbalance") or {}
        corr = float(ams.get("price_depth_corr") or 0.0)
        v = np.array(
            [
                t,
                float(lr.get("skewness") or 0.0),
                float(lr.get("kurtosis_excess") or 0.0),
                float(di.get("skewness") or 0.0),
                float(di.get("kurtosis_excess") or 0.0),
                corr,
            ],
            dtype=np.float64,
        ).reshape(1, -1)
        return v
    return None
