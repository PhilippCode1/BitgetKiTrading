"""
Gewichteter Composite-Score (vor Rejection) + Mikrostruktur-Konfluenz (VPIN, Orderbuch).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared_py.observability.orderbook_redis import read_orderbook_top5_pressures_0_1
from shared_py.observability.vpin_redis import (
    VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1,
    read_market_vpin_score_0_1,
)


def weighted_composite(
    structure: float,
    momentum: float,
    multi_tf: float,
    news: float,
    risk: float,
    history: float,
    weights: tuple[float, float, float, float, float, float],
) -> float:
    w_s, w_m, w_mt, w_n, w_r, w_h = weights
    raw = (
        structure * w_s
        + momentum * w_m
        + multi_tf * w_mt
        + news * w_n
        + risk * w_r
        + history * w_h
    )
    return max(0.0, min(100.0, raw))


@dataclass
class MicrostructureConfluenceResult:
    """Ergebnis von :func:`apply_microstructure_confluence`."""

    composite_0_100: float
    composite_pre_micro_0_100: float
    market_vpin_score_0_1: float | None
    orderbook_imbalance_ratio: float | None
    ask_pressure_0_1: float | None
    bid_pressure_0_1: float | None
    vpin_composite_scale: float
    rationale_lines: list[str] = field(default_factory=list)


def apply_microstructure_confluence(
    composite_0_100: float,
    *,
    symbol: str,
    redis_url: str,
) -> MicrostructureConfluenceResult:
    """
    Liest VPIN + Orderbuch-Druck aus Redis; bei VPIN > Schwellwert Composite * 0.5.

    Kein Redis / fehlende Keys: unveraendert, Metriken None.
    """
    pre = max(0.0, min(100.0, float(composite_0_100)))
    vpin = read_market_vpin_score_0_1(redis_url, symbol)
    ob = read_orderbook_top5_pressures_0_1(redis_url, symbol)

    imb: float | None = None
    ap: float | None = None
    bp: float | None = None
    if ob is not None:
        imb = ob.get("orderbook_imbalance_ratio")
        ap = ob.get("ask_pressure_0_1")
        bp = ob.get("bid_pressure_0_1")

    scale = 1.0
    if vpin is not None and vpin > VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1:
        scale = 0.5
    adjusted = max(0.0, min(100.0, pre * scale))

    lines: list[str] = []
    if vpin is not None:
        extra = ""
        if scale < 1.0:
            t = VPIN_ORDER_SIZE_REDUCE_THRESHOLD_0_1
            extra = f" (composite scaled x{scale} vpin>{t})"
        lines.append(f"market_vpin_score={vpin:.4f}{extra}")
    else:
        lines.append("market_vpin_score=null (no redis or key)")

    if ap is not None and bp is not None and imb is not None:
        lines.append(
            f"orderbook_imbalance_ratio={imb:+.3f} "
            f"bid_pressure_0_1={bp:.3f} ask_pressure_0_1={ap:.3f}"
        )
    else:
        lines.append("orderbook_pressures=null (no redis or key)")

    return MicrostructureConfluenceResult(
        composite_0_100=adjusted,
        composite_pre_micro_0_100=pre,
        market_vpin_score_0_1=vpin,
        orderbook_imbalance_ratio=imb,
        ask_pressure_0_1=ap,
        bid_pressure_0_1=bp,
        vpin_composite_scale=scale,
        rationale_lines=lines,
    )
