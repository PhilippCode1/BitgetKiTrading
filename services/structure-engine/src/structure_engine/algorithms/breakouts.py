from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Box:
    high: float
    low: float
    start_ts_ms: int
    end_ts_ms: int


def build_box(
    highs: list[float],
    lows: list[float],
    ts_ms: list[int],
    n_box: int,
) -> Box | None:
    if len(highs) < n_box or len(lows) < n_box or len(ts_ms) < n_box:
        return None
    h = highs[-n_box:]
    l = lows[-n_box:]
    t = ts_ms[-n_box:]
    return Box(
        high=max(h),
        low=min(l),
        start_ts_ms=t[0],
        end_ts_ms=t[-1],
    )


def prebreak_side(
    close: float,
    box: Box,
    prebreak_bps: float,
) -> str | None:
    if box.high <= box.low or close <= 0:
        return None
    dist_high_bps = ((box.high - close) / close) * 10_000.0
    dist_low_bps = ((close - box.low) / close) * 10_000.0
    if 0 <= dist_high_bps <= prebreak_bps:
        return "high"
    if 0 <= dist_low_bps <= prebreak_bps:
        return "low"
    return None


def buffer_at_price(price: float, buffer_bps: float) -> float:
    return abs(price) * (buffer_bps / 10_000.0)


@dataclass(frozen=True)
class FalseBreakoutState:
    side: str
    bars_remaining: int
    anchor_ts_ms: int


def parse_pending_false(raw: Any) -> FalseBreakoutState | None:
    if not isinstance(raw, dict):
        return None
    side = raw.get("side")
    if side not in ("up", "down"):
        return None
    try:
        bars = int(raw["bars_remaining"])
        anchor = int(raw["anchor_ts_ms"])
    except (KeyError, TypeError, ValueError):
        return None
    if bars < 0:
        return None
    return FalseBreakoutState(side=side, bars_remaining=bars, anchor_ts_ms=anchor)


def update_false_breakout_watch(
    *,
    close: float,
    box: Box,
    buffer_bps: float,
    window_bars: int,
    current_ts_ms: int,
    pending: FalseBreakoutState | None,
) -> tuple[FalseBreakoutState | None, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    buf_up = buffer_at_price(box.high, buffer_bps)
    buf_dn = buffer_at_price(box.low, buffer_bps)

    new_pending = pending
    if new_pending is not None:
        if new_pending.side == "up":
            if close <= box.high:
                events.append(
                    (
                        "FALSE_BREAKOUT",
                        {"side": "UP", "box_high": box.high, "close": close},
                    )
                )
                new_pending = None
            else:
                left = new_pending.bars_remaining - 1
                new_pending = None if left <= 0 else FalseBreakoutState(
                    side="up",
                    bars_remaining=left,
                    anchor_ts_ms=new_pending.anchor_ts_ms,
                )
        else:
            if close >= box.low:
                events.append(
                    (
                        "FALSE_BREAKOUT",
                        {"side": "DOWN", "box_low": box.low, "close": close},
                    )
                )
                new_pending = None
            else:
                left = new_pending.bars_remaining - 1
                new_pending = None if left <= 0 else FalseBreakoutState(
                    side="down",
                    bars_remaining=left,
                    anchor_ts_ms=new_pending.anchor_ts_ms,
                )
        return new_pending, events

    if close > box.high + buf_up:
        events.append(
            (
                "BREAKOUT",
                {"side": "UP", "box_high": box.high, "close": close},
            )
        )
        new_pending = FalseBreakoutState(
            side="up",
            bars_remaining=window_bars,
            anchor_ts_ms=current_ts_ms,
        )
    elif close < box.low - buf_dn:
        events.append(
            (
                "BREAKOUT",
                {"side": "DOWN", "box_low": box.low, "close": close},
            )
        )
        new_pending = FalseBreakoutState(
            side="down",
            bars_remaining=window_bars,
            anchor_ts_ms=current_ts_ms,
        )

    return new_pending, events


def box_to_json(
    box: Box,
    *,
    prebreak: str | None,
    pending: FalseBreakoutState | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "high": box.high,
        "low": box.low,
        "start_ts_ms": box.start_ts_ms,
        "end_ts_ms": box.end_ts_ms,
        "prebreak_side": prebreak,
    }
    if pending is not None:
        payload["pending_false"] = {
            "side": pending.side,
            "bars_remaining": pending.bars_remaining,
            "anchor_ts_ms": pending.anchor_ts_ms,
        }
    else:
        payload["pending_false"] = None
    return payload


def pending_from_json(payload: dict[str, Any]) -> FalseBreakoutState | None:
    return parse_pending_false(payload.get("pending_false"))
