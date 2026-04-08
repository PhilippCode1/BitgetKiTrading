from __future__ import annotations

from dataclasses import dataclass
from math import isnan
from typing import Sequence


@dataclass(frozen=True)
class OHLC:
    o: float
    h: float
    l: float
    c: float


def atr_sma(candles: Sequence[OHLC], window: int) -> float:
    if len(candles) < window + 1:
        return float("nan")
    trs: list[float] = []
    prev_close = candles[0].c
    for cur in candles[1:]:
        tr = max(cur.h - cur.l, abs(cur.h - prev_close), abs(cur.l - prev_close))
        trs.append(tr)
        prev_close = cur.c
    last = trs[-window:]
    return sum(last) / window


def atr_percent(atr: float, close: float) -> float:
    if isnan(atr) or close <= 0:
        return float("nan")
    return (atr / close) * 100.0
