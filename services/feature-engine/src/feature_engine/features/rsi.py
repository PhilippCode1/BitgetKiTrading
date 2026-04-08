from __future__ import annotations

from math import isnan
from typing import Sequence


def rsi_sma(closes: Sequence[float], window: int) -> float:
    if len(closes) < window + 1:
        return float("nan")
    changes = [cur - prev for prev, cur in zip(closes[:-1], closes[1:], strict=False)]
    recent = changes[-window:]
    gains = [change for change in recent if change > 0.0]
    losses = [-change for change in recent if change < 0.0]
    avg_gain = sum(gains) / window
    avg_loss = sum(losses) / window
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    value = 100.0 - (100.0 / (1.0 + rs))
    return 50.0 if isnan(value) else value
