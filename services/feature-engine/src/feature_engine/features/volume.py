from __future__ import annotations

from math import sqrt
from typing import Sequence


def volume_zscore(volumes: Sequence[float], window: int) -> float:
    if len(volumes) < window + 1:
        return float("nan")
    history = list(volumes[-window - 1 : -1])
    current = volumes[-1]
    mean = sum(history) / window
    variance = sum((value - mean) ** 2 for value in history) / window
    std = sqrt(variance)
    if std == 0.0:
        return 0.0
    return (current - mean) / std
