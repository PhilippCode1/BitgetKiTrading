from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from drawing_engine.algorithms.liquidity import (
    cluster_price_levels,
    parse_top25_side,
    topk_by_notional,
    zone_from_level_cluster,
)
from drawing_engine.algorithms.targets_stops import pick_zones_above, pick_zones_below
from drawing_engine.algorithms.trendlines import pick_trendline_points
from drawing_engine.algorithms.zones import (
    cluster_sorted_prices,
    confidence_from_touch_count,
    zone_from_cluster,
)
from drawing_engine.formatting import price_to_str
from drawing_engine.ids import stable_parent_id


def _default_style(drawing_type: str) -> dict[str, Any]:
    palette = {
        "support_zone": {"stroke": "#2ecc71", "fill": "#2ecc71", "fillOpacity": 0.12},
        "resistance_zone": {"stroke": "#e74c3c", "fill": "#e74c3c", "fillOpacity": 0.12},
        "trendline": {"stroke": "#3498db", "lineWidth": 2},
        "breakout_box": {"stroke": "#f39c12", "fill": "#f39c12", "fillOpacity": 0.08},
        "liquidity_zone": {"stroke": "#9b59b6", "fill": "#9b59b6", "fillOpacity": 0.1},
        "target_zone": {"stroke": "#1abc9c", "fill": "#1abc9c", "fillOpacity": 0.1},
        "stop_zone": {"stroke": "#c0392b", "fill": "#c0392b", "fillOpacity": 0.15},
    }
    return palette.get(drawing_type, {"stroke": "#95a5a6"})


def _horizontal_zone_geo(
    low: Decimal,
    high: Decimal,
    *,
    label: str | None = None,
    rank: int | None = None,
) -> dict[str, Any]:
    geo: dict[str, Any] = {
        "kind": "horizontal_zone",
        "price_low": price_to_str(low),
        "price_high": price_to_str(high),
    }
    if label is not None:
        geo["label"] = label
    if rank is not None:
        geo["rank"] = rank
    return geo


def _record(
    *,
    parent_id: str,
    revision: int,
    symbol: str,
    timeframe: str,
    drawing_type: str,
    geometry: dict[str, Any],
    confidence: float,
    reasons: list[str],
    ts_ms: int,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "drawing_id": str(uuid4()),
        "parent_id": parent_id,
        "revision": revision,
        "symbol": symbol,
        "timeframe": timeframe,
        "type": drawing_type,
        "status": "active",
        "geometry": geometry,
        "style": _default_style(drawing_type),
        "confidence": float(confidence),
        "reasons": reasons,
        "created_ts_ms": ts_ms,
        "updated_ts_ms": ts_ms,
    }


def build_drawing_records(
    *,
    symbol: str,
    timeframe: str,
    trend_dir: str,
    last_close: Decimal,
    swing_rows: list[dict[str, Any]],
    breakout_box: dict[str, Any] | None,
    bids_raw: Any,
    asks_raw: Any,
    zone_cluster_bps: Decimal,
    zone_pad_bps: Decimal,
    stop_pad_bps: Decimal,
    liquidity_topk: int,
    liquidity_cluster_bps: Decimal,
    ts_ms: int,
) -> list[dict[str, Any]]:
    lows_ts: list[tuple[int, Decimal]] = []
    highs_ts: list[tuple[int, Decimal]] = []
    for r in swing_rows:
        kind = str(r.get("kind", ""))
        try:
            px = Decimal(str(r["price"]))
            tsm = int(r["start_ts_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if kind == "low":
            lows_ts.append((tsm, px))
        elif kind == "high":
            highs_ts.append((tsm, px))

    low_prices = [p for _, p in lows_ts]
    high_prices = [p for _, p in highs_ts]

    out: list[dict[str, Any]] = []

    # --- Support / Resistance Zonen (Swing-Cluster) ---
    for idx, cluster in enumerate(cluster_sorted_prices(low_prices, cluster_bps=zone_cluster_bps)):
        zl, zh = zone_from_cluster(cluster, pad_bps=zone_pad_bps)
        pid = stable_parent_id(symbol, timeframe, "support", str(idx))
        conf = float(confidence_from_touch_count(len(cluster)))
        out.append(
            _record(
                parent_id=pid,
                revision=1,
                symbol=symbol,
                timeframe=timeframe,
                drawing_type="support_zone",
                geometry=_horizontal_zone_geo(zl, zh, label=f"support_{idx}"),
                confidence=conf,
                reasons=["swing_low_cluster", f"touch_count={len(cluster)}"],
                ts_ms=ts_ms,
            )
        )

    for idx, cluster in enumerate(cluster_sorted_prices(high_prices, cluster_bps=zone_cluster_bps)):
        zl, zh = zone_from_cluster(cluster, pad_bps=zone_pad_bps)
        pid = stable_parent_id(symbol, timeframe, "resistance", str(idx))
        conf = float(confidence_from_touch_count(len(cluster)))
        out.append(
            _record(
                parent_id=pid,
                revision=1,
                symbol=symbol,
                timeframe=timeframe,
                drawing_type="resistance_zone",
                geometry=_horizontal_zone_geo(zl, zh, label=f"resistance_{idx}"),
                confidence=conf,
                reasons=["swing_high_cluster", f"touch_count={len(cluster)}"],
                ts_ms=ts_ms,
            )
        )

    # --- Trendlinien ---
    if trend_dir == "UP" and len(lows_ts) >= 2:
        pair = pick_trendline_points(lows_ts, max_points=3)
        if pair is not None:
            (t0, p0), (t1, p1) = pair
            pid = stable_parent_id(symbol, timeframe, "trendline", "up")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="trendline",
                    geometry={
                        "kind": "two_point_line",
                        "direction": "up",
                        "point_a": {"t_ms": t0, "price": price_to_str(p0)},
                        "point_b": {"t_ms": t1, "price": price_to_str(p1)},
                    },
                    confidence=55.0,
                    reasons=["swing_lows_uptrend"],
                    ts_ms=ts_ms,
                )
            )
    elif trend_dir == "DOWN" and len(highs_ts) >= 2:
        pair = pick_trendline_points(highs_ts, max_points=3)
        if pair is not None:
            (t0, p0), (t1, p1) = pair
            pid = stable_parent_id(symbol, timeframe, "trendline", "down")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="trendline",
                    geometry={
                        "kind": "two_point_line",
                        "direction": "down",
                        "point_a": {"t_ms": t0, "price": price_to_str(p0)},
                        "point_b": {"t_ms": t1, "price": price_to_str(p1)},
                    },
                    confidence=55.0,
                    reasons=["swing_highs_downtrend"],
                    ts_ms=ts_ms,
                )
            )

    # --- Breakout-Box ---
    if breakout_box and breakout_box.get("high") is not None and breakout_box.get("low") is not None:
        try:
            bh = Decimal(str(breakout_box["high"]))
            bl = Decimal(str(breakout_box["low"]))
            t0 = int(breakout_box["start_ts_ms"])
            t1_raw = breakout_box.get("end_ts_ms")
            t1: int | None = int(t1_raw) if t1_raw is not None else None
        except (TypeError, ValueError):
            t1 = None
            bh = bl = Decimal(0)
        if bh > 0 and bl > 0:
            pid = stable_parent_id(symbol, timeframe, "breakout_box")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="breakout_box",
                    geometry={
                        "kind": "price_time_box",
                        "price_low": price_to_str(min(bl, bh)),
                        "price_high": price_to_str(max(bl, bh)),
                        "t_start_ms": t0,
                        "t_end_ms": t1,
                    },
                    confidence=60.0,
                    reasons=["structure_state_breakout_box"],
                    ts_ms=ts_ms,
                )
            )

    # --- Liquiditaet ---
    bids = parse_top25_side(bids_raw)
    asks = parse_top25_side(asks_raw)
    orderbook_ok = bool(bids or asks)

    if orderbook_ok:
        tb = topk_by_notional(bids, liquidity_topk)
        ta = topk_by_notional(asks, liquidity_topk)
        for side, levels, tag in (
            ("bid", tb, "bid"),
            ("ask", ta, "ask"),
        ):
            for cidx, cluster in enumerate(
                cluster_price_levels(levels, cluster_bps=liquidity_cluster_bps)
            ):
                zl, zh = zone_from_level_cluster(cluster, pad_bps=zone_pad_bps)
                pid = stable_parent_id(symbol, timeframe, "liquidity", side, str(cidx))
                out.append(
                    _record(
                        parent_id=pid,
                        revision=1,
                        symbol=symbol,
                        timeframe=timeframe,
                        drawing_type="liquidity_zone",
                        geometry=_horizontal_zone_geo(zl, zh, label=f"ob_{tag}_{cidx}"),
                        confidence=50.0,
                        reasons=["orderbook_top25", f"side={tag}"],
                        ts_ms=ts_ms,
                    )
                )
    else:
        for idx, cluster in enumerate(cluster_sorted_prices(low_prices, cluster_bps=zone_cluster_bps)[
            :3
        ]):
            zl, zh = zone_from_cluster(cluster, pad_bps=zone_pad_bps)
            pid = stable_parent_id(symbol, timeframe, "liquidity_fb", "low", str(idx))
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="liquidity_zone",
                    geometry=_horizontal_zone_geo(zl, zh, label=f"liq_fb_low_{idx}"),
                    confidence=35.0,
                    reasons=["liquidity_unspecified_orderbook", "swing_low_proxy"],
                    ts_ms=ts_ms,
                )
            )
        for idx, cluster in enumerate(cluster_sorted_prices(high_prices, cluster_bps=zone_cluster_bps)[
            :3
        ]):
            zl, zh = zone_from_cluster(cluster, pad_bps=zone_pad_bps)
            pid = stable_parent_id(symbol, timeframe, "liquidity_fb", "high", str(idx))
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="liquidity_zone",
                    geometry=_horizontal_zone_geo(zl, zh, label=f"liq_fb_high_{idx}"),
                    confidence=35.0,
                    reasons=["liquidity_unspecified_orderbook", "swing_high_proxy"],
                    ts_ms=ts_ms,
                )
            )

    # Support/Resistance Bounds fuer Targets
    support_bounds: list[tuple[Decimal, Decimal]] = []
    for cluster in cluster_sorted_prices(low_prices, cluster_bps=zone_cluster_bps):
        support_bounds.append(zone_from_cluster(cluster, pad_bps=zone_pad_bps))
    resist_bounds: list[tuple[Decimal, Decimal]] = []
    for cluster in cluster_sorted_prices(high_prices, cluster_bps=zone_cluster_bps):
        resist_bounds.append(zone_from_cluster(cluster, pad_bps=zone_pad_bps))

    # --- Targets & Stops ---
    if trend_dir == "UP":
        for rank, z in enumerate(pick_zones_above(last_close, resist_bounds)[:2], start=1):
            zl, zh = z
            pid = stable_parent_id(symbol, timeframe, "target", "up", str(rank))
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="target_zone",
                    geometry=_horizontal_zone_geo(zl, zh, rank=rank),
                    confidence=45.0,
                    reasons=["next_resistance_long_bias", f"rank={rank}"],
                    ts_ms=ts_ms,
                )
            )
        if lows_ts:
            last_low = max(lows_ts, key=lambda x: x[0])[1]
            pad = stop_pad_bps / Decimal(10000)
            sl = last_low * (Decimal(1) - pad)
            sh = last_low
            pid = stable_parent_id(symbol, timeframe, "stop", "long")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="stop_zone",
                    geometry=_horizontal_zone_geo(sl, sh, label="stop_long"),
                    confidence=40.0,
                    reasons=["invalidation_below_last_swing_low", "long_bias"],
                    ts_ms=ts_ms,
                )
            )
    elif trend_dir == "DOWN":
        for rank, z in enumerate(pick_zones_below(last_close, support_bounds)[:2], start=1):
            zl, zh = z
            pid = stable_parent_id(symbol, timeframe, "target", "down", str(rank))
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="target_zone",
                    geometry=_horizontal_zone_geo(zl, zh, rank=rank),
                    confidence=45.0,
                    reasons=["next_support_short_bias", f"rank={rank}"],
                    ts_ms=ts_ms,
                )
            )
        if highs_ts:
            last_high = max(highs_ts, key=lambda x: x[0])[1]
            pad = stop_pad_bps / Decimal(10000)
            sl = last_high
            sh = last_high * (Decimal(1) + pad)
            pid = stable_parent_id(symbol, timeframe, "stop", "short")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="stop_zone",
                    geometry=_horizontal_zone_geo(sl, sh, label="stop_short"),
                    confidence=40.0,
                    reasons=["invalidation_above_last_swing_high", "short_bias"],
                    ts_ms=ts_ms,
                )
            )
    else:
        above = pick_zones_above(last_close, resist_bounds)
        below = pick_zones_below(last_close, support_bounds)
        if above:
            zl, zh = above[0]
            pid = stable_parent_id(symbol, timeframe, "target", "range", "above")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="target_zone",
                    geometry=_horizontal_zone_geo(zl, zh, rank=1),
                    confidence=40.0,
                    reasons=["range_neutral_next_resistance"],
                    ts_ms=ts_ms,
                )
            )
        if below:
            zl, zh = below[0]
            pid = stable_parent_id(symbol, timeframe, "target", "range", "below")
            out.append(
                _record(
                    parent_id=pid,
                    revision=1,
                    symbol=symbol,
                    timeframe=timeframe,
                    drawing_type="target_zone",
                    geometry=_horizontal_zone_geo(zl, zh, rank=2),
                    confidence=40.0,
                    reasons=["range_neutral_next_support"],
                    ts_ms=ts_ms,
                )
            )

    return out
