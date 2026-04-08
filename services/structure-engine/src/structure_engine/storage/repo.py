from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from structure_engine.algorithms.swings import Candle
from structure_engine.algorithms.trend import SwingPrice


@dataclass(frozen=True)
class StoredCandle:
    symbol: str
    timeframe: str
    start_ts_ms: int
    o: float
    h: float
    l: float
    c: float


INSERT_SWING_SQL = """
INSERT INTO app.swings (
    swing_id, symbol, timeframe, start_ts_ms, kind, price, left_n, right_n, confirmed_ts_ms
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (symbol, timeframe, start_ts_ms, kind) DO NOTHING
RETURNING swing_id
"""

UPSERT_STATE_SQL = """
INSERT INTO app.structure_state (
    symbol, timeframe, last_ts_ms, trend_dir,
    last_swing_high_price, last_swing_low_price,
    compression_flag, breakout_box_json, updated_ts_ms,
    input_provenance_json
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
ON CONFLICT (symbol, timeframe) DO UPDATE SET
    last_ts_ms = EXCLUDED.last_ts_ms,
    trend_dir = EXCLUDED.trend_dir,
    last_swing_high_price = EXCLUDED.last_swing_high_price,
    last_swing_low_price = EXCLUDED.last_swing_low_price,
    compression_flag = EXCLUDED.compression_flag,
    breakout_box_json = EXCLUDED.breakout_box_json,
    updated_ts_ms = EXCLUDED.updated_ts_ms,
    input_provenance_json = EXCLUDED.input_provenance_json
"""

INSERT_EVENT_SQL = """
INSERT INTO app.structure_events (event_id, symbol, timeframe, ts_ms, type, details_json)
VALUES (%s, %s, %s, %s, %s, %s::jsonb)
"""


class StructureRepository:
    def __init__(self, database_url: str, *, logger: logging.Logger | None = None) -> None:
        self._database_url = database_url
        self._logger = logger or logging.getLogger("structure_engine.repo")

    def fetch_candles(
        self,
        *,
        symbol: str,
        timeframe: str,
        end_start_ts_ms: int,
        limit: int,
    ) -> list[StoredCandle]:
        sql = """
        SELECT symbol, timeframe, start_ts_ms,
               open AS o, high AS h, low AS l, close AS c
        FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s AND start_ts_ms <= %s
        ORDER BY start_ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, end_start_ts_ms, limit)).fetchall()
        rows.reverse()
        return [self._row_to_stored(row) for row in rows]

    def get_feature_row(
        self,
        *,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
    ) -> dict[str, Any] | None:
        sql = """
        SELECT atr_14, atrp_14
        FROM features.candle_features
        WHERE symbol = %s AND timeframe = %s AND start_ts_ms = %s
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, timeframe, start_ts_ms)).fetchone()
        return dict(row) if row else None

    def insert_swing_if_new(
        self,
        *,
        swing_id: UUID,
        symbol: str,
        timeframe: str,
        start_ts_ms: int,
        kind: str,
        price: float,
        left_n: int,
        right_n: int,
        confirmed_ts_ms: int,
    ) -> bool:
        with self._connect() as conn:
            with conn.transaction():
                row = conn.execute(
                    INSERT_SWING_SQL,
                    (
                        str(swing_id),
                        symbol,
                        timeframe,
                        start_ts_ms,
                        kind,
                        str(price),
                        left_n,
                        right_n,
                        confirmed_ts_ms,
                    ),
                ).fetchone()
                return row is not None

    def fetch_last_two_swings(
        self,
        *,
        symbol: str,
        timeframe: str,
        kind: str,
    ) -> list[SwingPrice]:
        sql = """
        SELECT start_ts_ms, price
        FROM app.swings
        WHERE symbol = %s AND timeframe = %s AND kind = %s
        ORDER BY start_ts_ms DESC
        LIMIT 2
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, kind)).fetchall()
        rows.reverse()
        return [
            SwingPrice(ts_ms=int(r["start_ts_ms"]), price=float(r["price"]))
            for r in rows
        ]

    def fetch_last_swing_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        kind: str,
    ) -> float | None:
        sql = """
        SELECT price
        FROM app.swings
        WHERE symbol = %s AND timeframe = %s AND kind = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, timeframe, kind)).fetchone()
        if row is None:
            return None
        return float(row["price"])

    def fetch_recent_swing_ids(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT swing_id, start_ts_ms, kind, price
        FROM app.swings
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, limit)).fetchall()
        out = []
        for r in reversed(rows):
            out.append(
                {
                    "swing_id": str(r["swing_id"]),
                    "start_ts_ms": int(r["start_ts_ms"]),
                    "kind": r["kind"],
                    "price": float(r["price"]),
                }
            )
        return out

    def get_structure_state_row(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        sql = """
        SELECT symbol, timeframe, last_ts_ms, trend_dir,
               last_swing_high_price, last_swing_low_price,
               compression_flag, breakout_box_json, updated_ts_ms,
               input_provenance_json
        FROM app.structure_state
        WHERE symbol = %s AND timeframe = %s
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, timeframe)).fetchone()
        return self._jsonify_state_row(row)

    def get_latest_structure_state(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        return self.get_structure_state_row(symbol=symbol, timeframe=timeframe)

    def fetch_recent_structure_events(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT event_id, ts_ms, type, details_json
        FROM app.structure_events
        WHERE symbol = %s AND timeframe = %s
        ORDER BY ts_ms DESC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, limit)).fetchall()
        out: list[dict[str, Any]] = []
        for r in reversed(rows):
            det = r["details_json"]
            if isinstance(det, str):
                det = json.loads(det)
            out.append(
                {
                    "event_id": str(r["event_id"]),
                    "ts_ms": int(r["ts_ms"]),
                    "type": r["type"],
                    "details": det,
                }
            )
        return out

    def upsert_structure_state(
        self,
        *,
        symbol: str,
        timeframe: str,
        last_ts_ms: int,
        trend_dir: str,
        last_swing_high_price: float | None,
        last_swing_low_price: float | None,
        compression_flag: bool,
        breakout_box_json: dict[str, Any],
        updated_ts_ms: int,
        input_provenance: dict[str, Any],
    ) -> None:
        payload = json.dumps(breakout_box_json, separators=(",", ":"), sort_keys=True)
        prov = json.dumps(input_provenance, separators=(",", ":"), sort_keys=True)
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    UPSERT_STATE_SQL,
                    (
                        symbol,
                        timeframe,
                        last_ts_ms,
                        trend_dir,
                        None if last_swing_high_price is None else str(last_swing_high_price),
                        None if last_swing_low_price is None else str(last_swing_low_price),
                        compression_flag,
                        payload,
                        updated_ts_ms,
                        prov,
                    ),
                )

    def insert_structure_event(
        self,
        *,
        event_id: UUID,
        symbol: str,
        timeframe: str,
        ts_ms: int,
        event_type: str,
        details: dict[str, Any],
    ) -> None:
        details_json = json.dumps(details, separators=(",", ":"), sort_keys=True)
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    INSERT_EVENT_SQL,
                    (
                        str(event_id),
                        symbol,
                        timeframe,
                        ts_ms,
                        event_type,
                        details_json,
                    ),
                )

    def _connect(
        self,
        *,
        row_factory: Any | None = None,
    ) -> psycopg.Connection[Any]:
        kwargs: dict[str, Any] = {"connect_timeout": 5, "autocommit": True}
        if row_factory is not None:
            kwargs["row_factory"] = row_factory
        return psycopg.connect(self._database_url, **kwargs)

    def _row_to_stored(self, row: dict[str, Any]) -> StoredCandle:
        return StoredCandle(
            symbol=str(row["symbol"]),
            timeframe=str(row["timeframe"]),
            start_ts_ms=int(row["start_ts_ms"]),
            o=float(row["o"]),
            h=float(row["h"]),
            l=float(row["l"]),
            c=float(row["c"]),
        )

    def _jsonify_state_row(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        for key in ("last_swing_high_price", "last_swing_low_price"):
            val = out.get(key)
            if isinstance(val, Decimal):
                out[key] = float(val)
            elif val is not None:
                out[key] = float(val)
        if isinstance(out.get("breakout_box_json"), str):
            out["breakout_box_json"] = json.loads(out["breakout_box_json"])
        ip = out.get("input_provenance_json")
        if isinstance(ip, str):
            out["input_provenance_json"] = json.loads(ip)
        return out


def stored_to_candles(rows: Sequence[StoredCandle]) -> list[Candle]:
    return [Candle(ts_ms=r.start_ts_ms, o=r.o, h=r.h, l=r.l, c=r.c) for r in rows]


def merge_candle_history(
    history: list[StoredCandle],
    current: StoredCandle,
) -> list[StoredCandle]:
    merged: dict[int, StoredCandle] = {c.start_ts_ms: c for c in history}
    merged[current.start_ts_ms] = current
    return [merged[k] for k in sorted(merged)]
