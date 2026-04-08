from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

import psycopg

TF_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1H": 3_600_000,
    "4H": 14_400_000,
}

CANONICAL_TFS: tuple[str, ...] = ("1m", "5m", "15m", "1H", "4H")


@dataclass
class FreshnessRow:
    datapoint: str
    last_ts_ms: int | None
    age_ms: int | None
    status: str
    details: dict[str, Any]


def _now_ms() -> int:
    return int(time.time() * 1000)


def classify_age(age_ms: int | None, thresh_ms: int) -> str:
    if age_ms is None:
        return "critical"
    if age_ms > thresh_ms:
        return "critical"
    if age_ms > int(thresh_ms * 0.7):
        return "warn"
    return "ok"


def detect_gap_count(timestamps_ms: Sequence[int], expected_interval_ms: int) -> int:
    """Letzte N Kerzen: Anzahl Luecken wenn Delta deutlich > erwartetes Intervall."""
    if len(timestamps_ms) < 2:
        return 0
    sorted_ts = sorted(timestamps_ms, reverse=True)
    gaps = 0
    max_jump = int(expected_interval_ms * 1.5)
    for i in range(len(sorted_ts) - 1):
        delta = sorted_ts[i] - sorted_ts[i + 1]
        if delta > max_jump:
            gaps += 1
    return gaps


def load_candle_rows(
    dsn: str,
    symbol: str,
    *,
    stale_thresholds_ms: dict[str, int],
    gap_lookback: int = 12,
) -> list[FreshnessRow]:
    now = _now_ms()
    out: list[FreshnessRow] = []
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        for tf in CANONICAL_TFS:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT max(start_ts_ms) FROM tsdb.candles
                    WHERE symbol = %s AND timeframe = %s
                    """,
                    (symbol, tf),
                )
                row = cur.fetchone()
                last = int(row[0]) if row and row[0] is not None else None
            age = now - last if last is not None else None
            thresh = stale_thresholds_ms.get(tf, stale_thresholds_ms.get(tf.lower(), 600_000))
            st = classify_age(age, thresh)
            gap_count = 0
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT start_ts_ms FROM tsdb.candles
                    WHERE symbol = %s AND timeframe = %s
                    ORDER BY start_ts_ms DESC
                    LIMIT %s
                    """,
                    (symbol, tf, gap_lookback),
                )
                ts_list = [int(r[0]) for r in cur.fetchall() if r[0] is not None]
            gap_count = detect_gap_count(ts_list, TF_INTERVAL_MS[tf])
            details: dict[str, Any] = {"timeframe": tf, "gap_count": gap_count}
            if gap_count > 0 and st == "ok":
                st = "warn"
            out.append(
                FreshnessRow(
                    datapoint=f"candles_{tf.lower()}",
                    last_ts_ms=last,
                    age_ms=age,
                    status=st,
                    details=details,
                )
            )
    return out


def load_signal_row(
    dsn: str,
    symbol: str,
    *,
    stale_ms: int,
) -> FreshnessRow:
    now = _now_ms()
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT max(analysis_ts_ms) FROM app.signals_v1
                WHERE symbol = %s AND timeframe = %s
                """,
                (symbol, "1m"),
            )
            row = cur.fetchone()
            last = int(row[0]) if row and row[0] is not None else None
    age = now - last if last is not None else None
    st = classify_age(age, stale_ms)
    return FreshnessRow(
        datapoint="signals",
        last_ts_ms=last,
        age_ms=age,
        status=st,
        details={"table": "app.signals_v1", "timeframe": "1m"},
    )


def load_drawing_row(
    dsn: str,
    symbol: str,
    *,
    stale_ms: int,
) -> FreshnessRow:
    now = _now_ms()
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT max((EXTRACT(EPOCH FROM updated_ts) * 1000)::bigint)
                FROM app.drawings
                WHERE symbol = %s AND timeframe = %s
                """,
                (symbol, "1m"),
            )
            row = cur.fetchone()
            last = int(row[0]) if row and row[0] is not None else None
    age = now - last if last is not None else None
    st = classify_age(age, stale_ms)
    return FreshnessRow(
        datapoint="drawings",
        last_ts_ms=last,
        age_ms=age,
        status=st,
        details={"timeframe": "1m"},
    )


def load_news_row(
    dsn: str,
    *,
    stale_ms: int,
) -> FreshnessRow:
    now = _now_ms()
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(published_ts_ms) FROM app.news_items")
            row = cur.fetchone()
            last = int(row[0]) if row and row[0] is not None else None
    age = now - last if last is not None else None
    st = classify_age(age, stale_ms)
    return FreshnessRow(
        datapoint="news",
        last_ts_ms=last,
        age_ms=age,
        status=st,
        details={},
    )


def load_funding_row(
    dsn: str,
    symbol: str,
    *,
    stale_ms: int,
) -> FreshnessRow:
    now = _now_ms()
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT max(ts_ms) FROM tsdb.funding_rate WHERE symbol = %s",
                (symbol,),
            )
            row = cur.fetchone()
            last = int(row[0]) if row and row[0] is not None else None
    age = now - last if last is not None else None
    st = classify_age(age, stale_ms)
    return FreshnessRow(
        datapoint="funding",
        last_ts_ms=last,
        age_ms=age,
        status=st,
        details={},
    )


def load_oi_row(
    dsn: str,
    symbol: str,
    *,
    stale_ms: int,
) -> FreshnessRow:
    now = _now_ms()
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT max(ts_ms) FROM tsdb.open_interest WHERE symbol = %s",
                (symbol,),
            )
            row = cur.fetchone()
            last = int(row[0]) if row and row[0] is not None else None
    age = now - last if last is not None else None
    st = classify_age(age, stale_ms)
    return FreshnessRow(
        datapoint="oi",
        last_ts_ms=last,
        age_ms=age,
        status=st,
        details={},
    )


def load_all_freshness(
    dsn: str,
    symbol: str,
    *,
    stale_thresholds: dict[str, int],
    signal_stale_ms: int,
    drawing_stale_ms: int,
    news_stale_ms: int,
    funding_stale_ms: int,
    oi_stale_ms: int,
) -> list[FreshnessRow]:
    candle_thresh = {
        "1m": stale_thresholds["1m"],
        "5m": stale_thresholds["5m"],
        "15m": stale_thresholds["15m"],
        "1H": stale_thresholds["1H"],
        "4H": stale_thresholds["4H"],
    }
    rows: list[FreshnessRow] = []
    rows.extend(load_candle_rows(dsn, symbol, stale_thresholds_ms=candle_thresh))
    rows.append(load_signal_row(dsn, symbol, stale_ms=signal_stale_ms))
    rows.append(load_drawing_row(dsn, symbol, stale_ms=drawing_stale_ms))
    rows.append(load_news_row(dsn, stale_ms=news_stale_ms))
    rows.append(load_funding_row(dsn, symbol, stale_ms=funding_stale_ms))
    rows.append(load_oi_row(dsn, symbol, stale_ms=oi_stale_ms))
    return rows
