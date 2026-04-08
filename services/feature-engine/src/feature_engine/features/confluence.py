from __future__ import annotations

from typing import Mapping

TIMEFRAME_WEIGHTS: dict[str, int] = {
    "1m": 1,
    "5m": 2,
    "15m": 3,
    "1H": 4,
    "4H": 5,
}


def confluence_score(
    latest_trend_dirs: Mapping[str, int],
    *,
    current_timeframe: str,
    current_trend_dir: int,
) -> float:
    if current_trend_dir == 0:
        return 50.0
    effective_trends = dict(latest_trend_dirs)
    effective_trends[current_timeframe] = current_trend_dir
    total_weight = sum(TIMEFRAME_WEIGHTS.values())
    points = 0.0
    for timeframe, weight in TIMEFRAME_WEIGHTS.items():
        direction = effective_trends.get(timeframe, 0)
        if direction == current_trend_dir:
            points += float(weight)
        elif direction == 0:
            points += float(weight) * 0.5
    return round((points / total_weight) * 100.0, 4)
