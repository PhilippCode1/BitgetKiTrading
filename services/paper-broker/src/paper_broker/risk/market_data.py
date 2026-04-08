from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg


def fetch_latest_atr(
    conn: psycopg.Connection[Any], symbol: str, timeframe: str
) -> tuple[Decimal | None, Decimal | None]:
    """(atr_14, atrp_14) aus features.candle_features."""
    row = conn.execute(
        """
        SELECT atr_14, atrp_14 FROM features.candle_features
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    if row is None or row[0] is None:
        return None, None
    try:
        atr = Decimal(str(row[0]))
    except Exception:
        atr = None
    try:
        atrp = Decimal(str(row[1])) if row[1] is not None else None
    except Exception:
        atrp = None
    return atr, atrp


def fetch_last_candle_hl(
    conn: psycopg.Connection[Any], symbol: str, timeframe: str
) -> tuple[Decimal | None, Decimal | None]:
    row = conn.execute(
        """
        SELECT high, low FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    if row is None:
        return None, None
    try:
        return Decimal(str(row[0])), Decimal(str(row[1]))
    except Exception:
        return None, None


def fetch_last_swing(
    conn: psycopg.Connection[Any], symbol: str, timeframe: str, kind: str
) -> tuple[Decimal | None, int | None]:
    row = conn.execute(
        """
        SELECT price, start_ts_ms FROM app.swings
        WHERE symbol = %s AND timeframe = %s AND kind = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol, timeframe, kind),
    ).fetchone()
    if row is None:
        return None, None
    try:
        return Decimal(str(row[0])), int(row[1])
    except Exception:
        return None, None


def fetch_stop_zone_drawing(
    conn: psycopg.Connection[Any], symbol: str, timeframe: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT drawing_id::text, geometry_json FROM app.drawings
        WHERE symbol = %s AND timeframe = %s AND status = 'active' AND type = 'stop_zone'
        ORDER BY updated_ts DESC
        LIMIT 1
        """,
        (symbol, timeframe),
    ).fetchone()
    if row is None:
        return None
    geo = row[1]
    if isinstance(geo, str):
        import json

        geo = json.loads(geo)
    if not isinstance(geo, dict):
        return None
    return {"drawing_id": row[0], "geometry": geo}


def fetch_target_zone_drawings(
    conn: psycopg.Connection[Any], symbol: str, timeframe: str, limit: int = 6
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT drawing_id::text, type, geometry_json FROM app.drawings
        WHERE symbol = %s AND timeframe = %s AND status = 'active'
          AND type IN ('target_zone', 'resistance_zone', 'support_zone')
        ORDER BY updated_ts DESC
        LIMIT %s
        """,
        (symbol, timeframe, limit),
    ).fetchall()
    out: list[dict[str, Any]] = []
    import json

    for r in rows or []:
        geo = r[2]
        if isinstance(geo, str):
            try:
                geo = json.loads(geo)
            except json.JSONDecodeError:
                continue
        if isinstance(geo, dict):
            out.append({"drawing_id": r[0], "type": r[1], "geometry": geo})
    return out


def zone_mid_price(geo: dict[str, Any]) -> Decimal | None:
    try:
        lo = Decimal(str(geo["price_low"]))
        hi = Decimal(str(geo["price_high"]))
        return (lo + hi) / Decimal("2")
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None


def fetch_orderbook_top_raw(
    conn: psycopg.Connection[Any], symbol: str
) -> tuple[Any, Any] | None:
    row = conn.execute(
        """
        SELECT bids_raw, asks_raw FROM tsdb.orderbook_top25
        WHERE symbol = %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    if row is None:
        return None
    return row[0], row[1]
