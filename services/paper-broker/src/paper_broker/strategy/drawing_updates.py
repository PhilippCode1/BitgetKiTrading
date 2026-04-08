from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.plan_service import parse_plan_json
from paper_broker.risk.quality_score import estimate_rr
from paper_broker.storage import repo_drawings, repo_position_events, repo_positions

logger = logging.getLogger("paper_broker.strategy.drawing")


def _meta_dict(m: Any) -> dict[str, Any]:
    if m is None:
        return {}
    if isinstance(m, dict):
        return dict(m)
    if isinstance(m, str):
        return json.loads(m) if m else {}
    return {}


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def maybe_update_tp_from_drawings(
    conn: psycopg.Connection[Any],
    *,
    settings: PaperBrokerSettings,
    symbol: str,
    timeframe: str,
    parent_ids: list[str],
    now_ms: int,
) -> int:
    """Aktualisiert TP2/TP3 wenn neue Zonen guenstiger. Returns count updated."""
    if not settings.use_drawing_target_updates or not parent_ids:
        return 0
    zones = repo_drawings.fetch_drawings_by_ids(conn, parent_ids)
    mids: list[tuple[Decimal, str]] = []
    for z in zones:
        if str(z.get("type", "")) not in ("target_zone", "resistance_zone", "support_zone"):
            continue
        mid = repo_drawings.zone_mid(z["geometry"])
        if mid is not None:
            mids.append((mid, str(z["drawing_id"])))

    updated = 0
    for pos in repo_positions.list_open_positions(conn):
        if str(pos["symbol"]).upper() != symbol.upper():
            continue
        tp_p = parse_plan_json(pos.get("tp_plan_json"))
        stop_p = parse_plan_json(pos.get("stop_plan_json"))
        if not tp_p or not tp_p.get("targets") or not stop_p:
            continue
        pos_tf = str(tp_p.get("timeframe") or timeframe)
        if pos_tf.lower() != timeframe.lower():
            continue
        side = str(pos["side"]).lower()
        entry = _dec(pos["entry_price_avg"])
        try:
            stop_px = _dec(stop_p["stop_price"])
        except Exception:
            continue
        targets = tp_p["targets"]
        if len(targets) < 3:
            continue
        exec_state = tp_p.get("execution_state") or {}
        hit = set(exec_state.get("hit_tp_indices") or [])
        if 2 in hit:
            continue

        if side == "long":
            cand = [(m, did) for m, did in mids if m > entry]
            cand.sort(key=lambda x: x[0])
        else:
            cand = [(m, did) for m, did in mids if m < entry]
            cand.sort(key=lambda x: x[0], reverse=True)
        if len(cand) < 2:
            continue

        old_rr = estimate_rr(entry, side, stop_px, tp_p)
        new_t2 = cand[0][0]
        new_t3 = cand[1][0] if len(cand) > 1 else cand[0][0]
        if side == "long":
            if new_t2 <= _dec(targets[1]["target_price"]):
                continue
        else:
            if new_t2 >= _dec(targets[1]["target_price"]):
                continue

        t2 = dict(targets[1])
        t3 = dict(targets[2])
        t2["target_price"] = str(new_t2)
        t2["drawing_id"] = cand[0][1]
        t3["target_price"] = str(new_t3)
        t3["drawing_id"] = cand[1][1] if len(cand) > 1 else cand[0][1]
        new_targets = [targets[0], t2, t3]
        tp_p["targets"] = new_targets
        new_rr = estimate_rr(entry, side, stop_px, tp_p)
        if old_rr is not None and new_rr is not None and new_rr < old_rr * Decimal("0.995"):
            logger.info("drawing_tp_skip_rr_regression position_id=%s", pos["position_id"])
            continue

        pid = UUID(str(pos["position_id"]))
        repo_positions.update_tp_plan_only(
            conn, pid, tp_plan_json=tp_p, plan_updated_ts_ms=now_ms
        )
        repo_position_events.insert_position_event(
            conn,
            position_id=pid,
            ts_ms=now_ms,
            event_type="PLAN_UPDATED",
            details={"source": "drawing_tp_updated", "parent_ids": parent_ids},
        )
        logger.info(
            "drawing_tp_updated position_id=%s symbol=%s timeframe=%s",
            pid,
            symbol,
            timeframe,
        )
        updated += 1
    return updated
