from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

LiquidityTier = Literal["TIER_1", "TIER_2", "TIER_3", "TIER_4", "TIER_5"]


@dataclass(frozen=True)
class LiquidityAssessment:
    symbol: str
    spread_bps: float | None
    slippage_buy_bps: float | None
    slippage_sell_bps: float | None
    depth_status: str
    liquidity_tier: LiquidityTier
    max_recommended_notional: float
    live_allowed: bool
    block_reasons: list[str]
    last_updated_utc: str


def compute_spread_bps(*, bid: float | None, ask: float | None) -> float | None:
    if bid is None or ask is None:
        return None
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    if mid <= 0:
        return None
    return ((ask - bid) / mid) * 10_000.0


def compute_vwap_slippage_bps(*, side: str, levels: list[dict], order_qty: float, reference_price: float) -> float | None:
    if order_qty <= 0 or reference_price <= 0:
        return None
    remaining = order_qty
    weighted_notional = 0.0
    consumed = 0.0
    for row in levels:
        price = float(row.get("price", 0.0))
        qty = float(row.get("qty", 0.0))
        if price <= 0 or qty <= 0:
            continue
        take = min(remaining, qty)
        weighted_notional += take * price
        consumed += take
        remaining -= take
        if remaining <= 0:
            break
    if consumed <= 0 or remaining > 0:
        return None
    vwap = weighted_notional / consumed
    if side.lower() == "buy":
        return ((vwap - reference_price) / reference_price) * 10_000.0
    return ((reference_price - vwap) / reference_price) * 10_000.0


def classify_liquidity_tier(
    *,
    spread_bps: float | None,
    slippage_buy_bps: float | None,
    slippage_sell_bps: float | None,
    depth_notional_top5: float,
    stale_orderbook: bool,
    status: str | None = None,
) -> LiquidityTier:
    state = str(status or "").lower()
    if state in {"delisted", "suspended", "unknown", "blocked", "quarantine"}:
        return "TIER_5"
    if stale_orderbook or spread_bps is None:
        return "TIER_4"
    buy_slippage = 9999.0 if slippage_buy_bps is None else slippage_buy_bps
    sell_slippage = 9999.0 if slippage_sell_bps is None else slippage_sell_bps
    max_slippage = max(buy_slippage, sell_slippage)
    if spread_bps <= 8 and max_slippage <= 12 and depth_notional_top5 >= 100_000:
        return "TIER_1"
    if spread_bps <= 18 and max_slippage <= 30 and depth_notional_top5 >= 40_000:
        return "TIER_2"
    if spread_bps <= 45 and max_slippage <= 90 and depth_notional_top5 >= 8_000:
        return "TIER_3"
    return "TIER_4"


def recommended_max_order_notional(*, liquidity_tier: LiquidityTier, depth_notional_top5: float) -> float:
    base = max(depth_notional_top5, 0.0)
    if liquidity_tier == "TIER_1":
        return min(base * 0.25, 25_000.0)
    if liquidity_tier == "TIER_2":
        return min(base * 0.15, 10_000.0)
    if liquidity_tier == "TIER_3":
        return min(base * 0.05, 1_500.0)
    return 0.0


def liquidity_blocks_live(
    *,
    liquidity_tier: LiquidityTier,
    stale_orderbook: bool,
    has_bids: bool,
    has_asks: bool,
    spread_bps: float | None,
    slippage_buy_bps: float | None,
    slippage_sell_bps: float | None,
    depth_sufficient: bool,
    requested_notional: float,
    max_recommended_notional: float,
    owner_approved_small_size: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if not has_bids and not has_asks:
        reasons.append("orderbook_fehlt")
    else:
        if not has_bids:
            reasons.append("bids_fehlen")
        if not has_asks:
            reasons.append("asks_fehlen")
    if stale_orderbook:
        reasons.append("orderbook_stale")
    if spread_bps is None:
        reasons.append("spread_unbekannt")
    elif spread_bps > 35:
        reasons.append("spread_zu_hoch")
    max_slippage = max(slippage_buy_bps or 9999.0, slippage_sell_bps or 9999.0)
    if slippage_buy_bps is None or slippage_sell_bps is None:
        reasons.append("slippage_unbekannt")
    elif max_slippage > 80:
        reasons.append("slippage_zu_hoch")
    if not depth_sufficient:
        reasons.append("depth_unzureichend")
    if requested_notional > max_recommended_notional:
        reasons.append("ordergroesse_ueber_liquiditaetsgrenze")
    if liquidity_tier in {"TIER_4", "TIER_5"}:
        reasons.append("liquiditaetstier_blockiert_live")
    if liquidity_tier == "TIER_3" and not owner_approved_small_size:
        reasons.append("tier3_ohne_owner_kleingroessenfreigabe")
    return list(dict.fromkeys(reasons))


def build_liquidity_block_reasons_de(reasons: list[str]) -> list[str]:
    mapping = {
        "orderbook_fehlt": "Orderbook fehlt; Live-Ausfuehrung ist gesperrt.",
        "bids_fehlen": "Bids fehlen; Kauf-/Verkaufsseite ist unvollstaendig.",
        "asks_fehlen": "Asks fehlen; Kauf-/Verkaufsseite ist unvollstaendig.",
        "orderbook_stale": "Orderbook ist stale; Live-Ausfuehrung ist gesperrt.",
        "spread_unbekannt": "Spread ist unbekannt; Live-Ausfuehrung ist gesperrt.",
        "spread_zu_hoch": "Spread liegt ueber der Sicherheitsgrenze.",
        "slippage_unbekannt": "Slippage ist unbekannt; Live-Ausfuehrung ist gesperrt.",
        "slippage_zu_hoch": "Erwartete VWAP-Slippage ist zu hoch.",
        "depth_unzureichend": "Top-N-Tiefe ist unzureichend fuer die geplante Ordergroesse.",
        "ordergroesse_ueber_liquiditaetsgrenze": "Geplante Ordergroesse ueberschreitet die empfohlene Liquiditaetsgrenze.",
        "liquiditaetstier_blockiert_live": "Liquiditaets-Tier blockiert Live-Opening.",
        "tier3_ohne_owner_kleingroessenfreigabe": "Tier-3-Asset braucht Owner-Freigabe fuer sehr kleine Live-Groessen.",
    }
    return [mapping.get(reason, f"Unbekannter Liquiditaetsblockgrund: {reason}") for reason in reasons]


def build_liquidity_assessment(
    *,
    symbol: str,
    bid: float | None,
    ask: float | None,
    bids: list[dict],
    asks: list[dict],
    orderbook_age_ms: int,
    max_orderbook_age_ms: int,
    planned_qty: float,
    requested_notional: float,
    status: str | None = None,
    owner_approved_small_size: bool = False,
) -> LiquidityAssessment:
    spread_bps = compute_spread_bps(bid=bid, ask=ask)
    ref_buy = ask if ask and ask > 0 else 0.0
    ref_sell = bid if bid and bid > 0 else 0.0
    slippage_buy = compute_vwap_slippage_bps(
        side="buy",
        levels=asks,
        order_qty=planned_qty,
        reference_price=ref_buy,
    )
    slippage_sell = compute_vwap_slippage_bps(
        side="sell",
        levels=bids,
        order_qty=planned_qty,
        reference_price=ref_sell,
    )
    depth_top5 = 0.0
    for row in (bids[:5] + asks[:5]):
        depth_top5 += float(row.get("price", 0.0)) * float(row.get("qty", 0.0))
    stale = orderbook_age_ms > max_orderbook_age_ms
    tier = classify_liquidity_tier(
        spread_bps=spread_bps,
        slippage_buy_bps=slippage_buy,
        slippage_sell_bps=slippage_sell,
        depth_notional_top5=depth_top5,
        stale_orderbook=stale,
        status=status,
    )
    max_notional = recommended_max_order_notional(liquidity_tier=tier, depth_notional_top5=depth_top5)
    reasons = liquidity_blocks_live(
        liquidity_tier=tier,
        stale_orderbook=stale,
        has_bids=len(bids) > 0,
        has_asks=len(asks) > 0,
        spread_bps=spread_bps,
        slippage_buy_bps=slippage_buy,
        slippage_sell_bps=slippage_sell,
        depth_sufficient=depth_top5 > 0,
        requested_notional=requested_notional,
        max_recommended_notional=max_notional,
        owner_approved_small_size=owner_approved_small_size,
    )
    return LiquidityAssessment(
        symbol=symbol.upper(),
        spread_bps=spread_bps,
        slippage_buy_bps=slippage_buy,
        slippage_sell_bps=slippage_sell,
        depth_status="ok" if depth_top5 > 0 else "insufficient",
        liquidity_tier=tier,
        max_recommended_notional=max_notional,
        live_allowed=len(reasons) == 0,
        block_reasons=reasons,
        last_updated_utc=datetime.now(tz=UTC).isoformat(),
    )
