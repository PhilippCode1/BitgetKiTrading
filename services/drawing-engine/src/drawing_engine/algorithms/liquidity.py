from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def parse_top25_side(raw: Any) -> list[tuple[Decimal, Decimal]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    out: list[tuple[Decimal, Decimal]] = []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        try:
            px = Decimal(str(row[0]))
            sz = Decimal(str(row[1]))
        except Exception:
            continue
        if px > 0 and sz >= 0:
            out.append((px, sz))
    return out


def topk_by_notional(
    levels: list[tuple[Decimal, Decimal]],
    k: int,
) -> list[tuple[Decimal, Decimal]]:
    scored = [(p * s, p, s) for p, s in levels if s > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [(p, s) for _, p, s in scored[:k]]


def cluster_price_levels(
    levels: Sequence[tuple[Decimal, Decimal]],
    *,
    cluster_bps: Decimal,
) -> list[list[tuple[Decimal, Decimal]]]:
    """
    Sortiert nach Preis, merged benachbarte Levels wenn Preisluecke relativ
    zum Mid <= cluster_bps.
    """
    if not levels:
        return []
    by_price = sorted(levels, key=lambda x: x[0])
    clusters: list[list[tuple[Decimal, Decimal]]] = []
    cur = [by_price[0]]

    def gap_bps(a: Decimal, b: Decimal) -> Decimal:
        lo, hi = (a, b) if a <= b else (b, a)
        mid = (lo + hi) / Decimal(2)
        if mid <= 0:
            return Decimal("999999")
        return (hi - lo) / mid * Decimal(10000)

    for item in by_price[1:]:
        last_px = cur[-1][0]
        if gap_bps(last_px, item[0]) <= cluster_bps:
            cur.append(item)
        else:
            clusters.append(cur)
            cur = [item]
    clusters.append(cur)
    return clusters


def zone_from_level_cluster(
    cluster: Sequence[tuple[Decimal, Decimal]],
    *,
    pad_bps: Decimal,
) -> tuple[Decimal, Decimal]:
    prices = [p for p, _ in cluster]
    m = min(prices)
    mx = max(prices)
    pad = pad_bps / Decimal(10000)
    return m * (Decimal(1) - pad), mx * (Decimal(1) + pad)
