"""
Orderbuch-Top5 aus Redis (Market-Stream) — Druck-Relation fuer Signal-Mikrostruktur.

Key: ``ms:orderbook_top5:{SYMBOL}`` (JSON: ts_ms, bids, asks [price, size]).
Berechnet Notionale, ``orderbook_imbalance_ratio`` in [-1,1], bid/ask-Druck 0..1.
"""

from __future__ import annotations

import json
import logging

from shared_py.redis_client import get_or_create_sync_pooled_client

logger = logging.getLogger("shared_py.observability.orderbook_redis")

ORDERBOOK_TOP5_REDIS_KEY_FMT = "ms:orderbook_top5:{symbol}"


def orderbook_top5_redis_key(symbol: str) -> str:
    s = str(symbol or "").strip().upper()
    return ORDERBOOK_TOP5_REDIS_KEY_FMT.format(symbol=s or "UNKNOWN")


def _notional_top(levels: list) -> float:
    total = 0.0
    for row in levels or []:
        if not isinstance(row, list | tuple) or len(row) < 2:
            continue
        try:
            p = float(row[0])
            sz = float(row[1])
        except (TypeError, ValueError):
            continue
        total += p * sz
    return max(0.0, total)


def read_orderbook_top5_pressures_0_1(
    redis_url: str,
    symbol: str,
) -> dict[str, float] | None:
    """
    Liest Druck-Metriken. Fehlschlag/kein Key -> None.
    """
    u = (redis_url or "").strip()
    if not u:
        return None
    key = orderbook_top5_redis_key(symbol)
    try:
        r = get_or_create_sync_pooled_client(u, role="orderbook_microstructure_read")
        raw = r.get(key)
    except Exception as exc:  # noqa: BLE001
        logger.debug("read_orderbook_top5_pressures %s: %s", key, exc)
        return None
    if raw in (None, ""):
        return None
    try:
        if isinstance(raw, bytes | bytearray):
            raw = raw.decode("utf-8", errors="replace")
        data = json.loads(str(raw)) if not isinstance(raw, dict) else raw
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.debug("orderbook top5 json parse: %s", exc)
        return None
    if not isinstance(data, dict):
        return None
    bids = data.get("bids")
    asks = data.get("asks")
    if not isinstance(bids, list) or not isinstance(asks, list):
        return None
    bid_d = _notional_top(bids)
    ask_d = _notional_top(asks)
    tot = bid_d + ask_d
    if tot <= 0:
        return None
    imbalance = (bid_d - ask_d) / tot
    return {
        "bid_pressure_0_1": max(0.0, min(1.0, bid_d / tot)),
        "ask_pressure_0_1": max(0.0, min(1.0, ask_d / tot)),
        "orderbook_imbalance_ratio": max(-1.0, min(1.0, imbalance)),
    }
