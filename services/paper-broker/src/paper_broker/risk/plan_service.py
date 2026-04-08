from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import psycopg

from paper_broker.config import PaperBrokerSettings
from paper_broker.risk.market_data import fetch_latest_atr
from paper_broker.risk.quality_score import compute_stop_quality, estimate_rr
from paper_broker.risk.stop_planner import build_stop_plan
from paper_broker.risk.tp_planner import build_tp_plan


def _position_meta_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def build_auto_plan_bundle(
    conn: psycopg.Connection[Any],
    *,
    position_row: dict[str, Any],
    settings: PaperBrokerSettings,
    timeframe: str,
    preferred_stop_trigger: str | None = None,
    method_mix: dict[str, bool] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], int, str | None]:
    symbol = str(position_row["symbol"])
    side = str(position_row["side"])
    entry = Decimal(str(position_row["entry_price_avg"]))
    qty = Decimal(str(position_row["qty_base"]))
    st_tr = preferred_stop_trigger or settings.stop_trigger_type_default
    stop_plan, atr_used = build_stop_plan(
        conn,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        entry=entry,
        settings=settings,
        trigger_type=st_tr,
        method_mix=method_mix,
    )
    _, atrp = fetch_latest_atr(conn, symbol, timeframe)
    meta = _position_meta_dict(position_row.get("meta"))
    efr = meta.get("exit_family_resolution")
    exit_hints = efr.get("execution_hints") if isinstance(efr, dict) else None
    tp_plan = build_tp_plan(
        conn,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        entry=entry,
        atr=atr_used,
        settings=settings,
        tp_trigger_default=settings.tp_trigger_type_default,
        initial_qty=qty,
        exit_execution_hints=exit_hints if isinstance(exit_hints, dict) else None,
    )
    try:
        sp = Decimal(str(stop_plan["stop_price"]))
    except Exception:
        sp = entry * (Decimal("1") - Decimal("0.01")) if side == "long" else entry * Decimal("1.01")
    rr = estimate_rr(entry, side, sp, tp_plan)
    score, warns = compute_stop_quality(
        entry=entry,
        side=side,
        stop_price=sp,
        atr=atr_used,
        stop_plan=stop_plan,
        tp_plan=tp_plan,
        atrp=atrp,
        settings=settings,
    )
    stop_plan["quality"] = {"stop_quality_score": score, "risk_warnings": warns}
    rr_s = str(rr) if rr is not None else None
    return stop_plan, tp_plan, score, rr_s


def parse_plan_json(raw: Any) -> dict[str, Any] | None:
    """JSON-Spalten stop_plan_json / tp_plan_json zu Dict; None bei fehlendem oder ungueltigem Inhalt."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return dict(parsed) if isinstance(parsed, dict) else None
    return None
