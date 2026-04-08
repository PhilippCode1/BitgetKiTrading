from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TrendDir = Literal["UP", "DOWN", "RANGE"]


@dataclass(frozen=True)
class SwingPrice:
    ts_ms: int
    price: float


def trend_from_swings(
    last_highs: list[SwingPrice],
    last_lows: list[SwingPrice],
) -> TrendDir:
    if len(last_highs) < 2 or len(last_lows) < 2:
        return "RANGE"
    h1, h2 = last_highs[-1], last_highs[-2]
    l1, l2 = last_lows[-1], last_lows[-2]
    higher_high = h1.price > h2.price
    higher_low = l1.price > l2.price
    lower_low = l1.price < l2.price
    lower_high = h1.price < h2.price
    if higher_high and higher_low:
        return "UP"
    if lower_low and lower_high:
        return "DOWN"
    return "RANGE"


def structure_event_on_bar_edge(
    trend: TrendDir,
    close: float,
    prev_close: float | None,
    last_swing_high: float | None,
    last_swing_low: float | None,
) -> tuple[str | None, str | None]:
    """
    Ein Event pro Bar-Uebergang (kein Spam solange die Bedingung mehrere Bars lang gilt).
    """
    if prev_close is None or last_swing_high is None or last_swing_low is None:
        return None, None
    if trend == "UP":
        if close > last_swing_high and prev_close <= last_swing_high:
            return "BOS", "UP"
        if close < last_swing_low and prev_close >= last_swing_low:
            return "CHOCH", "DOWN"
    elif trend == "DOWN":
        if close < last_swing_low and prev_close >= last_swing_low:
            return "BOS", "DOWN"
        if close > last_swing_high and prev_close <= last_swing_high:
            return "CHOCH", "UP"
    return None, None


def detect_bos_choch(
    trend: TrendDir,
    close: float,
    last_swing_high: float | None,
    last_swing_low: float | None,
) -> tuple[str | None, str | None]:
    """
    Returns (structure_event_type, detail_direction_key).
    type is 'BOS' or 'CHOCH'; direction in details_json.
    """
    if last_swing_high is None or last_swing_low is None:
        return None, None
    if trend == "UP":
        if close > last_swing_high:
            return "BOS", "UP"
        if close < last_swing_low:
            return "CHOCH", "DOWN"
    elif trend == "DOWN":
        if close < last_swing_low:
            return "BOS", "DOWN"
        if close > last_swing_high:
            return "CHOCH", "UP"
    return None, None
