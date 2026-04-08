from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Candle:
    ts_ms: int
    o: float
    h: float
    l: float
    c: float


@dataclass(frozen=True)
class Swing:
    ts_ms: int
    kind: str
    price: float


def detect_confirmed_swing(
    candles: Sequence[Candle],
    left_n: int,
    right_n: int,
) -> Swing | None:
    if len(candles) < left_n + right_n + 1:
        return None
    i = len(candles) - 1 - right_n
    if i < left_n or i < 0:
        return None
    window = candles[i - left_n : i + right_n + 1]
    hi = candles[i].h
    lo = candles[i].l
    if hi == max(c.h for c in window):
        return Swing(ts_ms=candles[i].ts_ms, kind="high", price=hi)
    if lo == min(c.l for c in window):
        return Swing(ts_ms=candles[i].ts_ms, kind="low", price=lo)
    return None


def confirmed_ts_ms(candles: Sequence[Candle]) -> int:
    return candles[-1].ts_ms
