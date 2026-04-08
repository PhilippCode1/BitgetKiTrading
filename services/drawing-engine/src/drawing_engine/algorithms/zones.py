from __future__ import annotations

from decimal import Decimal
from typing import Sequence


def cluster_sorted_prices(
    prices: Sequence[Decimal],
    *,
    cluster_bps: Decimal,
) -> list[list[Decimal]]:
    """
    Gruppiert sortierte Preise: solange (max-min)/mid*10000 <= cluster_bps.
    """
    if not prices:
        return []
    sorted_p = sorted(prices)
    clusters: list[list[Decimal]] = []
    current: list[Decimal] = [sorted_p[0]]

    def spread_bps(cluster: list[Decimal]) -> Decimal:
        m = min(cluster)
        mx = max(cluster)
        mid = (m + mx) / Decimal(2)
        if mid <= 0:
            return Decimal("999999")
        return (mx - m) / mid * Decimal(10000)

    for p in sorted_p[1:]:
        trial = current + [p]
        if spread_bps(trial) <= cluster_bps:
            current = trial
        else:
            clusters.append(current)
            current = [p]
    clusters.append(current)
    return clusters


def zone_from_cluster(
    cluster: Sequence[Decimal],
    *,
    pad_bps: Decimal,
) -> tuple[Decimal, Decimal]:
    m = min(cluster)
    mx = max(cluster)
    pad = pad_bps / Decimal(10000)
    low = m * (Decimal(1) - pad)
    high = mx * (Decimal(1) + pad)
    if low > high:
        low, high = high, low
    return low, high


def confidence_from_touch_count(n: int) -> int:
    return min(100, 20 + 15 * n)
