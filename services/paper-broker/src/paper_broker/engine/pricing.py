from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import httpx
import psycopg

from paper_broker.config import PaperBrokerSettings

logger = logging.getLogger("paper_broker.pricing")


def _d(x: Any) -> Decimal | None:
    if x is None:
        return None
    try:
        return Decimal(str(x))
    except Exception:
        return None


def load_orderbook_levels(
    conn: psycopg.Connection[Any],
    symbol: str,
    ts_ms: int | None,
    levels: int,
) -> tuple[list[tuple[Decimal, Decimal]], list[tuple[Decimal, Decimal]]] | None:
    """Liest tsdb.orderbook_levels bid/ask fuer einen Snapshot (letzter wenn ts_ms None)."""
    if ts_ms is None:
        row = conn.execute(
            """
            SELECT ts_ms FROM tsdb.orderbook_levels
            WHERE symbol = %s ORDER BY ts_ms DESC LIMIT 1
            """,
            (symbol,),
        ).fetchone()
        if row is None:
            return None
        ts_ms = int(row[0])
    bids: list[tuple[Decimal, Decimal]] = []
    asks: list[tuple[Decimal, Decimal]] = []
    rows = conn.execute(
        """
        SELECT side, level, price, size FROM tsdb.orderbook_levels
        WHERE symbol = %s AND ts_ms = %s AND level <= %s
        ORDER BY side, level ASC
        """,
        (symbol, ts_ms, levels),
    ).fetchall()
    if not rows:
        return None
    for side, _lvl, pr, sz in rows:
        p, s = _d(pr), _d(sz)
        if p is None or s is None:
            continue
        if str(side) == "bid":
            bids.append((p, s))
        else:
            asks.append((p, s))
    bids.sort(key=lambda x: x[0], reverse=True)
    asks.sort(key=lambda x: x[0])
    if not bids or not asks:
        return None
    return bids[:levels], asks[:levels]


def latest_ticker_prices(
    conn: psycopg.Connection[Any], symbol: str
) -> dict[str, Decimal | None]:
    row = conn.execute(
        """
        SELECT last_pr, bid_pr, ask_pr, mark_price, index_price, ts_ms
        FROM tsdb.ticker
        WHERE symbol = %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "last_pr": _d(row[0]),
        "bid_pr": _d(row[1]),
        "ask_pr": _d(row[2]),
        "mark_price": _d(row[3]),
        "index_price": _d(row[4]),
        "ts_ms": int(row[5]) if row[5] is not None else None,
    }


def fetch_bitget_symbol_price(settings: PaperBrokerSettings, symbol: str) -> dict[str, Decimal | None]:
    base = settings.bitget_api_base_url.rstrip("/")
    url = f"{base}{settings.endpoint_profile.public_ticker_path}"
    params = {"symbol": symbol}
    if settings.rest_product_type_param:
        params["productType"] = settings.bitget_product_type
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            body = r.json()
    except Exception as exc:
        logger.warning("symbol-price REST failed: %s", exc)
        return {}
    if isinstance(body, dict):
        bcode = body.get("code")
        if bcode not in (None, "00000"):
            msg = str(body.get("msg") or body.get("message") or "")[:300]
            logger.warning(
                "Bitget public ticker code=%s msg=%s symbol=%s (kein Signatur-Key noetig)",
                bcode,
                msg,
                symbol,
            )
            return {}
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, list) and data:
        item = data[0]
    elif isinstance(data, dict):
        item = data
    else:
        return {}
    if not isinstance(item, dict):
        return {}
    return {
        "last_pr": _d(item.get("price") or item.get("lastPr")),
        "mark_price": _d(item.get("markPrice")),
        "index_price": _d(item.get("indexPrice")),
        "bid_pr": _d(item.get("bidPr")),
        "ask_pr": _d(item.get("askPr")),
    }
