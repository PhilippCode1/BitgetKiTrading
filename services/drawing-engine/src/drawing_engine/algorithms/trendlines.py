from __future__ import annotations

from decimal import Decimal
from typing import Sequence


def pick_trendline_points(
    timed_prices: Sequence[tuple[int, Decimal]],
    *,
    max_points: int = 3,
) -> tuple[tuple[int, Decimal], tuple[int, Decimal]] | None:
    """
    Nimmt die letzten max_points Swing-Punkte (sortiert nach Zeit) und
    liefert aeltesten vs. juengsten Punkt als Trendlinie (2-Punkt).
    """
    if len(timed_prices) < 2:
        return None
    ordered = sorted(timed_prices, key=lambda x: x[0])
    tail = ordered[-max_points:] if len(ordered) > max_points else ordered
    return tail[0], tail[-1]
