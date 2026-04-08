from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import psycopg
from psycopg.rows import dict_row


def _ms_to_timestamptz(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)


def input_gates_from_drawing_provenance(prov: dict[str, Any] | None) -> dict[str, Any]:
    p = prov or {}
    cs = p.get("inherited_structure_candle_series") or {}
    ob = p.get("orderbook") or {}
    return {
        "ob_fresh": ob.get("fresh"),
        "struct_cov": cs.get("coverage_ok"),
        "struct_max_gap": cs.get("max_gap_bars"),
    }


def fingerprint_drawing(
    rec: dict[str, Any],
    *,
    input_gates: dict[str, Any] | None = None,
) -> str:
    subset: dict[str, Any] = {
        "type": rec["type"],
        "geometry": rec["geometry"],
        "style": rec["style"],
        "reasons": rec["reasons"],
        "confidence": rec["confidence"],
    }
    if input_gates is not None:
        subset["input_gates"] = input_gates
    return json.dumps(subset, sort_keys=True, separators=(",", ":"))


class DrawingRepository:
    def __init__(self, database_url: str, *, logger: logging.Logger | None = None) -> None:
        self._database_url = database_url
        self._logger = logger or logging.getLogger("drawing_engine.repo")

    def fetch_swings(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT start_ts_ms, kind, price
        FROM app.swings
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms ASC
        LIMIT %s
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe, limit)).fetchall()
        return [dict(r) for r in rows]

    def fetch_structure_state(
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
        if row is None:
            return None
        out = dict(row)
        if isinstance(out.get("breakout_box_json"), str):
            out["breakout_box_json"] = json.loads(out["breakout_box_json"])
        ip = out.get("input_provenance_json")
        if isinstance(ip, str):
            out["input_provenance_json"] = json.loads(ip)
        return out

    def fetch_latest_close(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> Decimal | None:
        sql = """
        SELECT close
        FROM tsdb.candles
        WHERE symbol = %s AND timeframe = %s
        ORDER BY start_ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol, timeframe)).fetchone()
        if row is None:
            return None
        return Decimal(str(row["close"]))

    def fetch_latest_orderbook_raw(
        self,
        *,
        symbol: str,
    ) -> tuple[Any, Any, int] | None:
        sql = """
        SELECT bids_raw, asks_raw, ts_ms
        FROM tsdb.orderbook_top25
        WHERE symbol = %s
        ORDER BY ts_ms DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (symbol,)).fetchone()
        if row is None:
            return None
        return row["bids_raw"], row["asks_raw"], int(row["ts_ms"])

    def list_active_parent_ids(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> set[str]:
        sql = """
        SELECT DISTINCT parent_id::text
        FROM app.drawings
        WHERE symbol = %s AND timeframe = %s AND status = 'active'
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe)).fetchall()
        return {r["parent_id"] for r in rows}

    def expire_active_not_in(
        self,
        *,
        symbol: str,
        timeframe: str,
        keep_parent_ids: set[str],
    ) -> int:
        if not keep_parent_ids:
            sql = """
            UPDATE app.drawings
            SET status = 'expired', updated_ts = now()
            WHERE symbol = %s AND timeframe = %s AND status = 'active'
            """
            with self._connect() as conn:
                with conn.transaction():
                    cur = conn.execute(sql, (symbol, timeframe))
                    return cur.rowcount
        ids = sorted(keep_parent_ids)
        placeholders = ", ".join(["%s"] * len(ids))
        sql = f"""
        UPDATE app.drawings
        SET status = 'expired', updated_ts = now()
        WHERE symbol = %s AND timeframe = %s AND status = 'active'
          AND parent_id::text NOT IN ({placeholders})
        """
        with self._connect() as conn:
            with conn.transaction():
                cur = conn.execute(sql, (symbol, timeframe, *ids))
                return cur.rowcount

    def max_revision(self, *, parent_id: str) -> int:
        sql = """
        SELECT COALESCE(MAX(revision), 0) AS m
        FROM app.drawings
        WHERE parent_id = %s
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (parent_id,)).fetchone()
        return int(row["m"]) if row else 0

    def latest_active_fingerprint(self, *, parent_id: str) -> str | None:
        sql = """
        SELECT geometry_json, style_json, reasons_json, confidence, type,
               input_provenance_json
        FROM app.drawings
        WHERE parent_id = %s AND status = 'active'
        ORDER BY revision DESC
        LIMIT 1
        """
        with self._connect(row_factory=dict_row) as conn:
            row = conn.execute(sql, (parent_id,)).fetchone()
        if row is None:
            return None
        reasons = row["reasons_json"]
        if isinstance(reasons, str):
            reasons = json.loads(reasons)
        rec = {
            "type": row["type"],
            "geometry": row["geometry_json"],
            "style": row["style_json"],
            "reasons": reasons,
            "confidence": float(row["confidence"]),
        }
        prov = row.get("input_provenance_json")
        if isinstance(prov, str):
            prov = json.loads(prov)
        gates = (
            input_gates_from_drawing_provenance(prov)
            if isinstance(prov, dict)
            else input_gates_from_drawing_provenance(None)
        )
        return fingerprint_drawing(rec, input_gates=gates)

    def expire_active_parent(self, *, parent_id: str) -> None:
        sql = """
        UPDATE app.drawings
        SET status = 'expired', updated_ts = now()
        WHERE parent_id = %s AND status = 'active'
        """
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(sql, (parent_id,))

    def insert_revision(
        self,
        *,
        drawing_id: str,
        parent_id: str,
        revision: int,
        symbol: str,
        timeframe: str,
        drawing_type: str,
        geometry: dict[str, Any],
        style: dict[str, Any],
        reasons: list[str],
        confidence: float,
        ts_ms: int,
        input_provenance: dict[str, Any] | None = None,
    ) -> None:
        sql = """
        INSERT INTO app.drawings (
            drawing_id, parent_id, revision, symbol, timeframe, type, status,
            geometry_json, style_json, reasons_json, confidence, created_ts, updated_ts,
            input_provenance_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, 'active',
            %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s,
            %s::jsonb
        )
        """
        ts = _ms_to_timestamptz(ts_ms)
        gj = json.dumps(geometry, separators=(",", ":"), sort_keys=True)
        sj = json.dumps(style, separators=(",", ":"), sort_keys=True)
        rj = json.dumps(reasons, separators=(",", ":"))
        prov = json.dumps(
            input_provenance or {},
            separators=(",", ":"),
            sort_keys=True,
        )
        with self._connect() as conn:
            with conn.transaction():
                conn.execute(
                    sql,
                    (
                        drawing_id,
                        parent_id,
                        revision,
                        symbol,
                        timeframe,
                        drawing_type,
                        gj,
                        sj,
                        rj,
                        str(confidence),
                        ts,
                        ts,
                        prov,
                    ),
                )

    def fetch_latest_active_records(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT DISTINCT ON (parent_id)
            drawing_id, parent_id, revision, symbol, timeframe, type, status,
            geometry_json, style_json, reasons_json, confidence,
            (EXTRACT(EPOCH FROM created_ts) * 1000)::bigint AS created_ts_ms,
            (EXTRACT(EPOCH FROM updated_ts) * 1000)::bigint AS updated_ts_ms
        FROM app.drawings
        WHERE symbol = %s AND timeframe = %s AND status = 'active'
        ORDER BY parent_id, revision DESC
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (symbol, timeframe)).fetchall()
        return [_row_to_api_dict(dict(r)) for r in rows]

    def fetch_history(
        self,
        *,
        parent_id: str,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
            drawing_id, parent_id, revision, symbol, timeframe, type, status,
            geometry_json, style_json, reasons_json, confidence,
            (EXTRACT(EPOCH FROM created_ts) * 1000)::bigint AS created_ts_ms,
            (EXTRACT(EPOCH FROM updated_ts) * 1000)::bigint AS updated_ts_ms
        FROM app.drawings
        WHERE parent_id = %s
        ORDER BY revision ASC
        """
        with self._connect(row_factory=dict_row) as conn:
            rows = conn.execute(sql, (parent_id,)).fetchall()
        return [_row_to_api_dict(dict(r)) for r in rows]

    def _connect(
        self,
        *,
        row_factory: Any | None = None,
    ) -> psycopg.Connection[Any]:
        kwargs: dict[str, Any] = {"connect_timeout": 5, "autocommit": True}
        if row_factory is not None:
            kwargs["row_factory"] = row_factory
        return psycopg.connect(self._database_url, **kwargs)


def _row_to_api_dict(row: dict[str, Any]) -> dict[str, Any]:
    reasons = row["reasons_json"]
    if isinstance(reasons, str):
        reasons = json.loads(reasons)
    return {
        "schema_version": "1.0",
        "drawing_id": str(row["drawing_id"]),
        "parent_id": str(row["parent_id"]),
        "revision": int(row["revision"]),
        "symbol": row["symbol"],
        "timeframe": row["timeframe"],
        "type": row["type"],
        "status": row["status"],
        "geometry": row["geometry_json"],
        "style": row["style_json"],
        "confidence": float(row["confidence"]),
        "reasons": reasons,
        "created_ts_ms": int(row["created_ts_ms"]),
        "updated_ts_ms": int(row["updated_ts_ms"]),
    }
