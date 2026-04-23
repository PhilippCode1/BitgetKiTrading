"""
Predatory / Maker-first Ausfuehrung: Post-Only am Best-Bid/Ask, Iceberg-Slices,
Slippage-Budget fuer Chase-Replace, Orderflow-Wall-Safety-Latch.

Chase (Cancel+Neu / Modify) und Folge-Tranchen nach Fill werden ausserhalb dieses
Moduls orchestriert; hier liegen die reinen Entscheidungs- und Planungsfunktionen.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

Side = Literal["buy", "sell"]


@dataclass(frozen=True)
class PassiveMakerParams:
    max_slippage_bps: float
    iceberg_slices: int
    imbalance_pause_ms: int
    imbalance_against_threshold: float


def passive_maker_trace_enabled(*, settings_default: bool, trace: dict[str, Any]) -> bool:
    """True wenn Market->Post-Only-Rewrite aktiv sein soll."""
    pm = trace.get("predatory_passive_maker")
    if pm is True:
        return True
    if isinstance(pm, dict):
        if "enabled" in pm:
            return bool(pm["enabled"])
        return bool(settings_default)
    return bool(settings_default)


def passive_params_from_sources(
    *,
    settings_max_slippage_bps: float,
    settings_slices: int,
    settings_imbalance_pause_ms: int,
    settings_imbalance_threshold: float,
    trace: dict[str, Any],
) -> PassiveMakerParams:
    pm = trace.get("predatory_passive_maker")
    d: dict[str, Any] = dict(pm) if isinstance(pm, dict) else {}
    return PassiveMakerParams(
        max_slippage_bps=float(d.get("max_slippage_bps", settings_max_slippage_bps)),
        iceberg_slices=int(d.get("iceberg_slices", settings_slices)),
        imbalance_pause_ms=int(d.get("imbalance_pause_ms", settings_imbalance_pause_ms)),
        imbalance_against_threshold=float(
            d.get("imbalance_against_threshold", settings_imbalance_threshold)
        ),
    )


def orderflow_wall_against_side(
    *,
    side: Side,
    orderflow_imbalance: float | None,
    threshold: float,
) -> bool:
    """
    Vereinfachtes Safety-Latch: starke Gegenseite im Orderbuch (Imbalance aus Prompt 16).

    Imbalance > 0 tendenziell bid-lastig; < 0 ask-lastig (Konvention wie VPIN-Seite).
    """
    if orderflow_imbalance is None:
        return False
    o = float(orderflow_imbalance)
    t = abs(float(threshold))
    if t <= 0.0:
        return False
    if side == "buy":
        return o < -t
    return o > t


def passive_limit_price(*, side: Side, bid: Decimal, ask: Decimal) -> Decimal:
    if side == "buy":
        return bid
    return ask


def chase_price_within_slippage(
    *,
    anchor_price: Decimal,
    new_limit_price: Decimal,
    max_slippage_bps: float,
) -> bool:
    """Absoluter Preisabstand vom Anchor vs. max_slippage_bps (fuer Long/Short gleich)."""
    if anchor_price <= 0 or new_limit_price <= 0:
        return False
    slip_bps = float(abs(new_limit_price - anchor_price) / anchor_price * Decimal(10000))
    return slip_bps <= float(max_slippage_bps) + 1e-9


def plan_iceberg_sizes(total: Decimal, slices: int, rng: random.Random) -> list[Decimal]:
    """
    Zerlegt `total` in `slices` Teile mit Gewichten in [0.8, 1.2] (+-20%),
    normalisiert so dass die Summe exakt `total` ist.
    """
    n = max(1, int(slices))
    if total <= 0:
        return []
    if n == 1:
        return [total]
    weights = [Decimal(str(round(0.8 + 0.4 * rng.random(), 12))) for _ in range(n)]
    wsum = sum(weights)
    if wsum <= 0:
        return [total]
    raw = [total * (w / wsum) for w in weights]
    s = sum(raw)
    drift = total - s
    raw[-1] = raw[-1] + drift
    return raw


def coalesce_orderflow_imbalance(trace: dict[str, Any]) -> float | None:
    """Liest orderflow_imbalance aus flachem Trace oder Microstructure-Nesting."""
    for key in ("orderflow_imbalance_5", "orderflow_imbalance_10"):
        v = trace.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    ms = trace.get("microstructure") or trace.get("orderbook_micro")
    if isinstance(ms, dict):
        v = ms.get("orderflow_imbalance_5")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def passive_anchor_decimal(trace: dict[str, Any], fallback_price: str | None) -> Decimal | None:
    raw = trace.get("passive_anchor_price")
    if raw is None:
        pm = trace.get("predatory_passive_maker")
        if isinstance(pm, dict):
            raw = pm.get("passive_anchor_price")
    if raw is None and fallback_price:
        raw = fallback_price
    if raw is None:
        return None
    try:
        d = Decimal(str(raw))
    except Exception:
        return None
    return d if d > 0 else None
