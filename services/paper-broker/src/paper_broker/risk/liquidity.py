from __future__ import annotations

import json
from decimal import Decimal
from typing import Any


def _parse_levels(raw: Any) -> list[tuple[Decimal, Decimal]]:
    """[[priceStr, sizeStr], ...] -> [(price, size)]"""
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
            p = Decimal(str(row[0]))
            s = Decimal(str(row[1]))
        except Exception:
            continue
        out.append((p, s))
    return out


def notional_density_peak_near(
    *,
    candidate: Decimal,
    side: str,
    bids_raw: Any,
    asks_raw: Any,
    scan_bps: Decimal,
    entry: Decimal,
) -> tuple[Decimal | None, Decimal]:
    """
    Sucht Preis-Level mit hoechster Notional-Dichte im Band um candidate.
    Gibt (cluster_price, max_notional) zurueck.
    """
    band = entry * scan_bps / Decimal("10000")
    lo, hi = candidate - band, candidate + band
    peak_p: Decimal | None = None
    peak_n = Decimal("0")
    for price, size in _parse_levels(bids_raw) + _parse_levels(asks_raw):
        if price < lo or price > hi:
            continue
        n = abs(price * size)
        if n > peak_n:
            peak_n = n
            peak_p = price
    return peak_p, peak_n


def escape_stop_from_liquidity(
    *,
    candidate: Decimal,
    side: str,
    entry: Decimal,
    bids_raw: Any,
    asks_raw: Any,
    scan_bps: Decimal,
    escape_bps: Decimal,
    avoid_bps: Decimal,
) -> tuple[Decimal, dict[str, Any]]:
    """
    Long-Stop unter Entry: wenn Cluster zu nahe an candidate, Stop nach unten schieben.
    Short: Stop ueber Entry, Schieben nach oben.
    """
    basis: dict[str, Any] = {
        "nearest_liq_zone": None,
        "distance_bps": None,
        "adjusted_by_bps": "0",
    }
    cl_p, _mx = notional_density_peak_near(
        candidate=candidate,
        side=side,
        bids_raw=bids_raw,
        asks_raw=asks_raw,
        scan_bps=scan_bps,
        entry=entry,
    )
    if cl_p is None:
        return candidate, basis
    dist_bps = abs(cl_p - candidate) / entry * Decimal("10000")
    basis["nearest_liq_zone"] = str(cl_p)
    basis["distance_bps"] = str(dist_bps)
    if dist_bps > avoid_bps:
        return candidate, basis
    adj = entry * escape_bps / Decimal("10000")
    if side.lower() == "long":
        new_stop = candidate - adj
        basis["adjusted_by_bps"] = str(escape_bps)
        return new_stop, basis
    new_stop = candidate + adj
    basis["adjusted_by_bps"] = str(escape_bps)
    return new_stop, basis
