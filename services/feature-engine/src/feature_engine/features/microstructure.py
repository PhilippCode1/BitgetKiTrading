from __future__ import annotations

from dataclasses import dataclass

from feature_engine.storage.repo import FundingSnapshot, OpenInterestSnapshot, OrderBookSnapshot, TickerSnapshot

SLIPPAGE_BUCKETS_USDT = (5_000, 10_000)


@dataclass(frozen=True)
class MarketContextFeatures:
    spread_bps: float | None
    bid_depth_usdt_top25: float | None
    ask_depth_usdt_top25: float | None
    orderbook_imbalance: float | None
    depth_balance_ratio: float | None
    depth_to_bar_volume_ratio: float | None
    impact_buy_bps_5000: float | None
    impact_sell_bps_5000: float | None
    impact_buy_bps_10000: float | None
    impact_sell_bps_10000: float | None
    execution_cost_bps: float | None
    volatility_cost_bps: float | None
    funding_rate: float | None
    funding_rate_bps: float | None
    funding_cost_bps_window: float | None
    funding_time_to_next_ms: int | None
    open_interest: float | None
    open_interest_change_pct: float | None
    mark_index_spread_bps: float | None
    basis_bps: float | None
    orderbook_age_ms: int | None
    funding_age_ms: int | None
    open_interest_age_ms: int | None
    liquidity_source: str | None
    funding_source: str | None
    open_interest_source: str | None


def build_market_context_features(
    *,
    market_family: str,
    orderbook: OrderBookSnapshot | None,
    ticker: TickerSnapshot | None,
    funding: FundingSnapshot | None,
    open_interest: OpenInterestSnapshot | None,
    previous_open_interest: OpenInterestSnapshot | None,
    candle_usdt_vol: float,
    timeframe_ms: int,
    analysis_ts_ms: int,
    atrp_14: float | None,
    supports_funding: bool = True,
    supports_open_interest: bool = True,
) -> MarketContextFeatures:
    liquidity = _liquidity_features(
        orderbook=orderbook,
        ticker=ticker,
        candle_usdt_vol=candle_usdt_vol,
        analysis_ts_ms=analysis_ts_ms,
    )
    funding_metrics = _funding_features(
        market_family=market_family,
        funding=funding,
        timeframe_ms=timeframe_ms,
        analysis_ts_ms=analysis_ts_ms,
        supports_funding=supports_funding,
    )
    oi_metrics = _open_interest_features(
        market_family=market_family,
        current=open_interest,
        previous=previous_open_interest,
        analysis_ts_ms=analysis_ts_ms,
        supports_open_interest=supports_open_interest,
    )
    execution_cost_bps = liquidity["execution_cost_bps"]
    volatility_cost_bps = None
    if execution_cost_bps is not None:
        volatility_multiplier = 1.0
        if atrp_14 is not None and atrp_14 > 0:
            volatility_multiplier += atrp_14 / 100.0
        volatility_cost_bps = execution_cost_bps * volatility_multiplier
    family_metrics = _family_features(
        market_family=market_family,
        ticker=ticker,
        funding=funding,
        analysis_ts_ms=analysis_ts_ms,
        supports_funding=supports_funding,
        supports_open_interest=supports_open_interest,
    )
    return MarketContextFeatures(
        spread_bps=liquidity["spread_bps"],
        bid_depth_usdt_top25=liquidity["bid_depth_usdt_top25"],
        ask_depth_usdt_top25=liquidity["ask_depth_usdt_top25"],
        orderbook_imbalance=liquidity["orderbook_imbalance"],
        depth_balance_ratio=liquidity["depth_balance_ratio"],
        depth_to_bar_volume_ratio=liquidity["depth_to_bar_volume_ratio"],
        impact_buy_bps_5000=liquidity["impact_buy_bps_5000"],
        impact_sell_bps_5000=liquidity["impact_sell_bps_5000"],
        impact_buy_bps_10000=liquidity["impact_buy_bps_10000"],
        impact_sell_bps_10000=liquidity["impact_sell_bps_10000"],
        execution_cost_bps=execution_cost_bps,
        volatility_cost_bps=volatility_cost_bps,
        funding_rate=funding_metrics["funding_rate"],
        funding_rate_bps=funding_metrics["funding_rate_bps"],
        funding_cost_bps_window=funding_metrics["funding_cost_bps_window"],
        funding_time_to_next_ms=family_metrics["funding_time_to_next_ms"],
        open_interest=oi_metrics["open_interest"],
        open_interest_change_pct=oi_metrics["open_interest_change_pct"],
        mark_index_spread_bps=family_metrics["mark_index_spread_bps"],
        basis_bps=family_metrics["basis_bps"],
        orderbook_age_ms=liquidity["orderbook_age_ms"],
        funding_age_ms=funding_metrics["funding_age_ms"],
        open_interest_age_ms=oi_metrics["open_interest_age_ms"],
        liquidity_source=liquidity["liquidity_source"],
        funding_source=funding_metrics["funding_source"],
        open_interest_source=oi_metrics["open_interest_source"],
    )


def _liquidity_features(
    *,
    orderbook: OrderBookSnapshot | None,
    ticker: TickerSnapshot | None,
    candle_usdt_vol: float,
    analysis_ts_ms: int,
) -> dict[str, float | int | str | None]:
    if orderbook and orderbook.bids and orderbook.asks:
        metrics = _book_metrics(
            bids=orderbook.bids,
            asks=orderbook.asks,
            candle_usdt_vol=candle_usdt_vol,
        )
        return {
            **metrics,
            "orderbook_age_ms": max(0, analysis_ts_ms - orderbook.ts_ms),
            "liquidity_source": orderbook.source,
        }

    if ticker and ticker.bid_pr and ticker.ask_pr and ticker.bid_pr > 0 and ticker.ask_pr > 0:
        bid_depth = ticker.bid_pr * ticker.bid_sz if ticker.bid_sz and ticker.bid_sz > 0 else None
        ask_depth = ticker.ask_pr * ticker.ask_sz if ticker.ask_sz and ticker.ask_sz > 0 else None
        total_depth = (bid_depth or 0.0) + (ask_depth or 0.0)
        mid = (ticker.bid_pr + ticker.ask_pr) / 2.0
        spread_bps = 0.0 if mid <= 0 else ((ticker.ask_pr - ticker.bid_pr) / mid) * 10_000.0
        imbalance = None
        depth_balance_ratio = None
        if total_depth > 0 and bid_depth is not None and ask_depth is not None:
            imbalance = (bid_depth - ask_depth) / total_depth
            depth_balance_ratio = min(bid_depth, ask_depth) / max(bid_depth, ask_depth)
        depth_to_volume = None
        if total_depth > 0 and candle_usdt_vol > 0:
            depth_to_volume = total_depth / candle_usdt_vol
        return {
            "spread_bps": spread_bps,
            "bid_depth_usdt_top25": bid_depth,
            "ask_depth_usdt_top25": ask_depth,
            "orderbook_imbalance": imbalance,
            "depth_balance_ratio": depth_balance_ratio,
            "depth_to_bar_volume_ratio": depth_to_volume,
            "impact_buy_bps_5000": None,
            "impact_sell_bps_5000": None,
            "impact_buy_bps_10000": None,
            "impact_sell_bps_10000": None,
            "execution_cost_bps": spread_bps,
            "orderbook_age_ms": max(0, analysis_ts_ms - ticker.ts_ms),
            "liquidity_source": f"ticker:{ticker.source}",
        }

    return {
        "spread_bps": None,
        "bid_depth_usdt_top25": None,
        "ask_depth_usdt_top25": None,
        "orderbook_imbalance": None,
        "depth_balance_ratio": None,
        "depth_to_bar_volume_ratio": None,
        "impact_buy_bps_5000": None,
        "impact_sell_bps_5000": None,
        "impact_buy_bps_10000": None,
        "impact_sell_bps_10000": None,
        "execution_cost_bps": None,
        "orderbook_age_ms": None,
        "liquidity_source": "missing",
    }


def _book_metrics(
    *,
    bids: list[tuple[float, float]],
    asks: list[tuple[float, float]],
    candle_usdt_vol: float,
) -> dict[str, float | None]:
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        return {
            "spread_bps": None,
            "bid_depth_usdt_top25": None,
            "ask_depth_usdt_top25": None,
            "orderbook_imbalance": None,
            "depth_balance_ratio": None,
            "depth_to_bar_volume_ratio": None,
            "impact_buy_bps_5000": None,
            "impact_sell_bps_5000": None,
            "impact_buy_bps_10000": None,
            "impact_sell_bps_10000": None,
            "execution_cost_bps": None,
        }
    mid = (best_bid + best_ask) / 2.0
    spread_bps = 0.0 if mid <= 0 else ((best_ask - best_bid) / mid) * 10_000.0
    bid_depth = _depth_notional(bids)
    ask_depth = _depth_notional(asks)
    total_depth = bid_depth + ask_depth
    imbalance = None if total_depth <= 0 else (bid_depth - ask_depth) / total_depth
    depth_balance_ratio = None
    if bid_depth > 0 and ask_depth > 0:
        depth_balance_ratio = min(bid_depth, ask_depth) / max(bid_depth, ask_depth)
    depth_to_volume = None
    if candle_usdt_vol > 0 and total_depth > 0:
        depth_to_volume = total_depth / candle_usdt_vol
    impacts: dict[str, float | None] = {}
    impact_values: list[float] = []
    for size in SLIPPAGE_BUCKETS_USDT:
        buy_fill = _price_to_fill(asks, float(size))
        sell_fill = _price_to_fill(bids, float(size))
        buy_key = f"impact_buy_bps_{size}"
        sell_key = f"impact_sell_bps_{size}"
        buy_impact = None if buy_fill is None or mid <= 0 else ((buy_fill - mid) / mid) * 10_000.0
        sell_impact = None if sell_fill is None or mid <= 0 else ((mid - sell_fill) / mid) * 10_000.0
        impacts[buy_key] = buy_impact
        impacts[sell_key] = sell_impact
        if buy_impact is not None:
            impact_values.append(buy_impact)
        if sell_impact is not None:
            impact_values.append(sell_impact)
    execution_cost_bps = spread_bps
    if impact_values:
        execution_cost_bps += sum(impact_values) / len(impact_values)
    return {
        "spread_bps": spread_bps,
        "bid_depth_usdt_top25": bid_depth,
        "ask_depth_usdt_top25": ask_depth,
        "orderbook_imbalance": imbalance,
        "depth_balance_ratio": depth_balance_ratio,
        "depth_to_bar_volume_ratio": depth_to_volume,
        "impact_buy_bps_5000": impacts.get("impact_buy_bps_5000"),
        "impact_sell_bps_5000": impacts.get("impact_sell_bps_5000"),
        "impact_buy_bps_10000": impacts.get("impact_buy_bps_10000"),
        "impact_sell_bps_10000": impacts.get("impact_sell_bps_10000"),
        "execution_cost_bps": execution_cost_bps,
    }


def _funding_features(
    *,
    market_family: str,
    funding: FundingSnapshot | None,
    timeframe_ms: int,
    analysis_ts_ms: int,
    supports_funding: bool,
) -> dict[str, float | int | str | None]:
    if market_family != "futures":
        return {
            "funding_rate": None,
            "funding_rate_bps": None,
            "funding_cost_bps_window": None,
            "funding_age_ms": None,
            "funding_source": "not_applicable",
        }
    if not supports_funding:
        return {
            "funding_rate": None,
            "funding_rate_bps": None,
            "funding_cost_bps_window": None,
            "funding_age_ms": None,
            "funding_source": "not_applicable",
        }
    if funding is None:
        return {
            "funding_rate": None,
            "funding_rate_bps": None,
            "funding_cost_bps_window": None,
            "funding_age_ms": None,
            "funding_source": "missing",
        }
    interval_hours = funding.interval_hours or 8
    interval_ms = max(1, interval_hours * 60 * 60 * 1000)
    funding_rate_bps = funding.funding_rate * 10_000.0
    funding_cost_bps_window = abs(funding_rate_bps) * (timeframe_ms / interval_ms)
    return {
        "funding_rate": funding.funding_rate,
        "funding_rate_bps": funding_rate_bps,
        "funding_cost_bps_window": funding_cost_bps_window,
        "funding_age_ms": max(0, analysis_ts_ms - funding.ts_ms),
        "funding_source": funding.source,
    }


def _open_interest_features(
    *,
    market_family: str,
    current: OpenInterestSnapshot | None,
    previous: OpenInterestSnapshot | None,
    analysis_ts_ms: int,
    supports_open_interest: bool,
) -> dict[str, float | int | str | None]:
    if market_family != "futures":
        return {
            "open_interest": None,
            "open_interest_change_pct": None,
            "open_interest_age_ms": None,
            "open_interest_source": "not_applicable",
        }
    if not supports_open_interest:
        return {
            "open_interest": None,
            "open_interest_change_pct": None,
            "open_interest_age_ms": None,
            "open_interest_source": "not_applicable",
        }
    if current is None:
        return {
            "open_interest": None,
            "open_interest_change_pct": None,
            "open_interest_age_ms": None,
            "open_interest_source": "missing",
        }
    change_pct = None
    if previous is not None and previous.size > 0:
        change_pct = ((current.size - previous.size) / previous.size) * 100.0
    return {
        "open_interest": current.size,
        "open_interest_change_pct": change_pct,
        "open_interest_age_ms": max(0, analysis_ts_ms - current.ts_ms),
        "open_interest_source": current.source,
    }


def _family_features(
    *,
    market_family: str,
    ticker: TickerSnapshot | None,
    funding: FundingSnapshot | None,
    analysis_ts_ms: int,
    supports_funding: bool,
    supports_open_interest: bool,
) -> dict[str, float | int | None]:
    if market_family != "futures":
        return {
            "mark_index_spread_bps": None,
            "basis_bps": None,
            "funding_time_to_next_ms": None,
        }
    mark_index_spread_bps = None
    basis_bps = None
    if ticker is not None and ticker.index_price is not None and ticker.index_price > 0:
        if ticker.mark_price is not None:
            mark_index_spread_bps = ((ticker.mark_price - ticker.index_price) / ticker.index_price) * 10_000.0
        if ticker.last_pr is not None:
            basis_bps = ((ticker.last_pr - ticker.index_price) / ticker.index_price) * 10_000.0
    funding_time_to_next_ms = None
    if (
        supports_funding
        and funding is not None
        and funding.next_update_ms is not None
    ):
        funding_time_to_next_ms = max(0, funding.next_update_ms - analysis_ts_ms)
    return {
        "mark_index_spread_bps": mark_index_spread_bps,
        "basis_bps": basis_bps,
        "funding_time_to_next_ms": funding_time_to_next_ms,
    }


def _depth_notional(levels: list[tuple[float, float]]) -> float:
    total = 0.0
    for price, size in levels:
        if price <= 0 or size <= 0:
            continue
        total += price * size
    return total


def _price_to_fill(levels: list[tuple[float, float]], target_notional_usdt: float) -> float | None:
    cumulative = 0.0
    for price, size in levels:
        if price <= 0 or size <= 0:
            continue
        cumulative += price * size
        if cumulative >= target_notional_usdt:
            return price
    return None
