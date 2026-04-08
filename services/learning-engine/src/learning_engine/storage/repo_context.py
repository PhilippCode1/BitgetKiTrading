from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "1H": 3_600_000,
    "4h": 14_400_000,
    "4H": 14_400_000,
}


def fetch_position(conn: psycopg.Connection[Any], position_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM paper.positions WHERE position_id = %s",
        (str(position_id),),
    ).fetchone()
    return dict(row) if row else None


def fetch_fills_ordered(conn: psycopg.Connection[Any], position_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT f.* FROM paper.fills f
        WHERE f.position_id = %s
        ORDER BY f.ts_ms ASC
        """,
        (str(position_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def sum_fees(conn: psycopg.Connection[Any], position_id: UUID) -> Decimal:
    row = conn.execute(
        "SELECT COALESCE(SUM(fee_usdt), 0) AS s FROM paper.fee_ledger WHERE position_id = %s",
        (str(position_id),),
    ).fetchone()
    return Decimal(str(row["s"])) if row else Decimal("0")


def sum_funding(conn: psycopg.Connection[Any], position_id: UUID) -> Decimal:
    row = conn.execute(
        "SELECT COALESCE(SUM(funding_usdt), 0) AS s FROM paper.funding_ledger WHERE position_id = %s",
        (str(position_id),),
    ).fetchone()
    return Decimal(str(row["s"])) if row else Decimal("0")


def fetch_position_events(conn: psycopg.Connection[Any], position_id: UUID) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM paper.position_events
        WHERE position_id = %s
        ORDER BY ts_ms ASC
        """,
        (str(position_id),),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_signal_v1(conn: psycopg.Connection[Any], signal_id: UUID) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM app.signals_v1 WHERE signal_id = %s",
        (str(signal_id),),
    ).fetchone()
    return dict(row) if row else None


def fetch_strategy_state(conn: psycopg.Connection[Any], key: str) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM paper.strategy_state WHERE key = %s",
        (key,),
    ).fetchone()
    return dict(row) if row else None


def fetch_structure_state(
    conn: psycopg.Connection[Any],
    symbol: str,
    timeframe: str,
    *,
    max_ts_ms: int | None = None,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM app.structure_state
        WHERE symbol = %s AND timeframe = ANY(%s)
        """,
        (symbol, _timeframe_aliases(timeframe)),
    ).fetchone()
    if not row:
        return None
    out = dict(row)
    if max_ts_ms is not None and int(out.get("last_ts_ms") or 0) > int(max_ts_ms):
        return None
    return out


def fetch_structure_events_around(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    open_ts_ms: int,
    until_ts_ms: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM app.structure_events
        WHERE symbol = %s AND timeframe = ANY(%s) AND ts_ms >= %s AND ts_ms <= %s
        ORDER BY ts_ms ASC
        """,
        (symbol, _timeframe_aliases(timeframe), open_ts_ms, until_ts_ms),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_structure_events_before(
    conn: psycopg.Connection[Any], *, symbol: str, timeframe: str, ts_ms: int, limit: int = 20
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM app.structure_events
        WHERE symbol = %s AND timeframe = ANY(%s) AND ts_ms <= %s
        ORDER BY ts_ms DESC
        LIMIT %s
        """,
        (symbol, _timeframe_aliases(timeframe), ts_ms, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_features_near(
    conn: psycopg.Connection[Any], *, symbol: str, timeframe: str, ts_ms: int
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM features.candle_features
        WHERE symbol = %s AND timeframe = ANY(%s) AND start_ts_ms <= %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol, _timeframe_aliases(timeframe), ts_ms),
    ).fetchone()
    return dict(row) if row else None


def fetch_latest_candle_before(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    ts_ms: int,
) -> dict[str, Any] | None:
    tf_ms = _timeframe_ms(timeframe)
    row = conn.execute(
        """
        SELECT symbol, timeframe, start_ts_ms, open, high, low, close,
               base_vol, quote_vol, usdt_vol
        FROM tsdb.candles
        WHERE symbol = %s
          AND timeframe = %s
          AND start_ts_ms + %s <= %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """,
        (symbol, timeframe, tf_ms, ts_ms),
    ).fetchone()
    return dict(row) if row else None


def fetch_candles_window(
    conn: psycopg.Connection[Any],
    *,
    symbol: str,
    timeframe: str,
    start_ts_ms: int,
    end_ts_ms: int,
) -> list[dict[str, Any]]:
    tf_ms = _timeframe_ms(timeframe)
    rows = conn.execute(
        """
        SELECT symbol, timeframe, start_ts_ms, open, high, low, close,
               base_vol, quote_vol, usdt_vol
        FROM tsdb.candles
        WHERE symbol = %s
          AND timeframe = %s
          AND start_ts_ms >= %s
          AND start_ts_ms + %s <= %s
        ORDER BY start_ts_ms ASC
        """,
        (symbol, timeframe, start_ts_ms, tf_ms, end_ts_ms),
    ).fetchall()
    return [dict(r) for r in rows]


def fetch_news_window(
    conn: psycopg.Connection[Any], *, start_ms: int, end_ms: int, limit: int = 30
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT news_id, title, relevance_score, sentiment, impact_window,
               published_ts_ms, scored_ts_ms
        FROM app.news_items
        WHERE COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) >= %s
          AND COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms, 0) <= %s
        ORDER BY COALESCE(scored_ts_ms, published_ts_ms, ingested_ts_ms) DESC
        LIMIT %s
        """,
        (start_ms, end_ms, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def has_news_shock_strategy_event(conn: psycopg.Connection[Any], position_id: UUID) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM paper.strategy_events
        WHERE type = 'NEWS_SHOCK'
          AND details->>'position_id' = %s
        LIMIT 1
        """,
        (str(position_id),),
    ).fetchone()
    return row is not None


def _parse_jsonb(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    return val


def meta_dict(meta: Any) -> dict[str, Any]:
    m = _parse_jsonb(meta)
    return dict(m) if isinstance(m, dict) else {}


def _timeframe_aliases(timeframe: str) -> list[str]:
    tf = str(timeframe).strip()
    aliases = {tf}
    if tf == "1H":
        aliases.add("1h")
    elif tf == "4H":
        aliases.add("4h")
    return sorted(aliases)


def _timeframe_ms(timeframe: str) -> int:
    tf = str(timeframe).strip()
    try:
        return TIMEFRAME_TO_MS[tf]
    except KeyError as exc:
        raise ValueError(f"unsupported timeframe: {timeframe!r}") from exc
