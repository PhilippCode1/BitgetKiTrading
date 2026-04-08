from __future__ import annotations

from decimal import Decimal
from typing import Sequence


def pick_zones_above(
    ref: Decimal,
    zone_bounds: Sequence[tuple[Decimal, Decimal]],
) -> list[tuple[Decimal, Decimal]]:
    """Zonen komplett oberhalb ref, sortiert aufsteigend nach unterer Kante."""
    above = [z for z in zone_bounds if z[0] > ref]
    above.sort(key=lambda z: z[0])
    return above


def pick_zones_below(
    ref: Decimal,
    zone_bounds: Sequence[tuple[Decimal, Decimal]],
) -> list[tuple[Decimal, Decimal]]:
    below = [z for z in zone_bounds if z[1] < ref]
    below.sort(key=lambda z: z[1], reverse=True)
    return below
