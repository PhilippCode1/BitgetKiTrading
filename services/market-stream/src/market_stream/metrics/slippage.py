from __future__ import annotations

from decimal import Decimal

LevelPair = tuple[str, str]


def compute_slippage_metrics(
    *,
    symbol: str,
    ts_ms: int,
    bids: list[LevelPair],
    asks: list[LevelPair],
    sizes_usdt: list[int],
    top_n: int,
) -> dict[str, object]:
    if not bids or not asks:
        raise ValueError("slippage metrics benoetigen mindestens eine Bid- und Ask-Stufe")

    limited_bids = bids[:top_n]
    limited_asks = asks[:top_n]

    best_bid = Decimal(limited_bids[0][0])
    best_ask = Decimal(limited_asks[0][0])
    mid = (best_bid + best_ask) / Decimal("2")
    spread_abs = best_ask - best_bid
    spread_bps = Decimal("0") if mid == 0 else (spread_abs / mid) * Decimal("10000")

    bid_depth_usdt = _depth_notional(limited_bids)
    ask_depth_usdt = _depth_notional(limited_asks)
    total_depth = bid_depth_usdt + ask_depth_usdt
    imbalance = (
        Decimal("0")
        if total_depth == 0
        else (bid_depth_usdt - ask_depth_usdt) / total_depth
    )

    payload: dict[str, object] = {
        "symbol": symbol,
        "ts_ms": ts_ms,
        "top_n": top_n,
        "best_bid": str(best_bid),
        "best_ask": str(best_ask),
        "mid": str(mid),
        "spread_abs": str(spread_abs),
        "spread_bps": str(spread_bps),
        "bid_depth_usdt_topN": str(bid_depth_usdt),
        "ask_depth_usdt_topN": str(ask_depth_usdt),
        "imbalance": str(imbalance),
    }

    for size_usdt in sizes_usdt:
        target = Decimal(size_usdt)
        buy_fill_price = _price_to_fill(limited_asks, target)
        sell_fill_price = _price_to_fill(limited_bids, target)
        payload[f"fill_buy_price_{size_usdt}_usdt"] = (
            None if buy_fill_price is None else str(buy_fill_price)
        )
        payload[f"fill_sell_price_{size_usdt}_usdt"] = (
            None if sell_fill_price is None else str(sell_fill_price)
        )
        payload[f"impact_buy_bps_{size_usdt}_usdt"] = (
            None
            if buy_fill_price is None or mid == 0
            else str(((buy_fill_price - mid) / mid) * Decimal("10000"))
        )
        payload[f"impact_sell_bps_{size_usdt}_usdt"] = (
            None
            if sell_fill_price is None or mid == 0
            else str(((mid - sell_fill_price) / mid) * Decimal("10000"))
        )

    return payload


def _depth_notional(levels: list[LevelPair]) -> Decimal:
    total = Decimal("0")
    for price, size in levels:
        total += Decimal(price) * Decimal(size)
    return total


def _price_to_fill(levels: list[LevelPair], target_notional_usdt: Decimal) -> Decimal | None:
    cumulative = Decimal("0")
    for price, size in levels:
        level_notional = Decimal(price) * Decimal(size)
        cumulative += level_notional
        if cumulative >= target_notional_usdt:
            return Decimal(price)
    return None
