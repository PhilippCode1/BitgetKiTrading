from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Json


def insert_tsfm_war_room_audit(conn: psycopg.Connection, row: dict[str, Any]) -> str:
    """Persistiert eine War-Room/TimesFM-Zeile; ``outcome_*`` optional spaeter."""
    sql = """
        INSERT INTO learn.tsfm_war_room_audit (
            recorded_ts_ms, symbol, forecast_sha256, tsfm_direction,
            tsfm_confidence_0_1, tsfm_horizon_ticks,
            quant_action, quant_confidence_0_1, quant_confidence_effective_0_1,
            macro_action, macro_news_shock,
            consensus_action, consensus_status,
            quant_weight_base, quant_weight_effective, shock_penalty_applied,
            anchor_price, quant_foundation_path_ms, war_room_eval_wall_ms,
            outcome_return_pct, outcome_eval_ts_ms, payload
        ) VALUES (
            %(recorded_ts_ms)s, %(symbol)s, %(forecast_sha256)s, %(tsfm_direction)s,
            %(tsfm_confidence_0_1)s, %(tsfm_horizon_ticks)s,
            %(quant_action)s, %(quant_confidence_0_1)s, %(quant_confidence_effective_0_1)s,
            %(macro_action)s, %(macro_news_shock)s,
            %(consensus_action)s, %(consensus_status)s,
            %(quant_weight_base)s, %(quant_weight_effective)s, %(shock_penalty_applied)s,
            %(anchor_price)s, %(quant_foundation_path_ms)s, %(war_room_eval_wall_ms)s,
            %(outcome_return_pct)s, %(outcome_eval_ts_ms)s, %(payload)s
        )
        RETURNING audit_id
    """
    params = dict(row)
    params["payload"] = Json(params.get("payload") or {})
    with conn.cursor() as cur:
        cur.execute(sql, params)
        one = cur.fetchone()
    if not one:
        raise RuntimeError("insert_tsfm_war_room_audit: keine audit_id")
    return str(one.get("audit_id") or "")
