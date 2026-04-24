"""
AI-Reasoning-Attribution: strategy_signal_explain vs. 4h-Kerzen und P&L (Prompt 70).
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from shared_py.post_trade_review import (
    build_attribution_post_trade_review,
    classify_reasoning_quality,
    evaluate_thesis_vs_candles,
    extract_reference_level_from_strategy_result,
)

from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_post_trade_review
from learning_engine.storage.repo_context import fetch_candles_window

logger = logging.getLogger("learning_engine.ai_attribution")


def _j(x: Any) -> Any:
    if isinstance(x, str):
        try:
            return json.loads(x)
        except json.JSONDecodeError:
            return x
    return x


def _fetch_execution_id_for_signal(
    conn: psycopg.Connection[Any], signal_id: UUID
) -> UUID | None:
    row = conn.execute(
        """
        SELECT execution_id
        FROM live.execution_decisions
        WHERE source_signal_id = %s::uuid
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (str(signal_id),),
    ).fetchone()
    if row is None or row.get("execution_id") is None:
        return None
    try:
        return UUID(str(row["execution_id"]))
    except (TypeError, ValueError):
        return None


def _fetch_strategy_explain_log(
    conn: psycopg.Connection[Any],
    *,
    execution_id: UUID | None,
    signal_id: UUID,
) -> dict[str, Any] | None:
    if execution_id is not None:
        row = conn.execute(
            """
            SELECT log_id, response_json, created_ts
            FROM public.ai_evaluation_logs
            WHERE task_type = 'strategy_signal_explain'
              AND execution_id = %s::uuid
            ORDER BY created_ts DESC
            LIMIT 1
            """,
            (str(execution_id),),
        ).fetchone()
        if row:
            return dict(row)
    row = conn.execute(
        """
        SELECT log_id, response_json, created_ts
        FROM public.ai_evaluation_logs
        WHERE task_type = 'strategy_signal_explain'
          AND source_signal_id = %s::uuid
        ORDER BY created_ts DESC
        LIMIT 1
        """,
        (str(signal_id),),
    ).fetchone()
    return dict(row) if row else None


def run_ai_attribution_for_evaluation(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    evaluation_id: UUID,
    eval_row: dict[str, Any],
    sig_row: dict[str, Any] | None,
    decision_ts_ms: int,
    primary_timeframe: str,
) -> None:
    if not settings.learn_ai_attribution_enabled:
        return
    raw_sid = eval_row.get("signal_id")
    if raw_sid is None:
        return
    try:
        signal_id = UUID(str(raw_sid))
    except (TypeError, ValueError):
        return

    ex_id = _fetch_execution_id_for_signal(conn, signal_id)
    log_row = _fetch_strategy_explain_log(conn, execution_id=ex_id, signal_id=signal_id)
    response: dict[str, Any] = {}
    if log_row:
        response = _j(log_row.get("response_json")) or {}
        if not isinstance(response, dict):
            response = {}
    result = response.get("result")
    if not isinstance(result, dict):
        result = {}

    scenario = (
        (result.get("expected_scenario_de") or "")
        or (result.get("strategy_explanation_de") or "")
    )[:4000]

    ref, _src, role = extract_reference_level_from_strategy_result(result)

    sym = str(eval_row.get("symbol") or "").upper()
    side = str(eval_row.get("side") or "").lower()
    pnl = Decimal(str(eval_row.get("pnl_net_usdt") or "0"))
    w_ms = int(settings.learn_ai_attribution_window_ms)
    t0 = (
        int(decision_ts_ms)
        if decision_ts_ms > 0
        else int(eval_row.get("opened_ts_ms") or 0)
    )
    t1 = t0 + w_ms
    if t0 <= 0 or not sym:
        logger.info("ai_attribution skip: bad window or symbol eval=%s", evaluation_id)
        return

    candles: list[dict[str, Any]] = []
    try:
        candles = fetch_candles_window(
            conn,
            symbol=sym,
            timeframe=str(primary_timeframe or "5m"),
            start_ts_ms=t0,
            end_ts_ms=t1,
        )
    except Exception as exc:
        logger.warning("ai_attribution candles eval=%s: %s", evaluation_id, exc)

    thesis_holds: bool | None = None
    eval_meta: dict[str, Any] = {"candle_count": len(candles), "level_source": _src}
    if ref is not None and candles:
        thesis_holds, eval_meta = evaluate_thesis_vs_candles(
            side=side,
            reference_price=ref,
            role=role,
            candles=candles,
        )
    elif ref is None:
        thesis_holds = None
    else:
        thesis_holds = None

    label, accuracy = classify_reasoning_quality(pnl_net=pnl, thesis_holds=thesis_holds)
    review = build_attribution_post_trade_review(
        quality_label=label,
        pnl_net=pnl,
        scenario_excerpt=scenario,
        thesis_holds=thesis_holds,
        meta=eval_meta,
    )

    row = {
        "signal_id": str(signal_id),
        "execution_id": str(ex_id) if ex_id else None,
        "trade_evaluation_id": str(evaluation_id),
        "scenario_excerpt_de": scenario or None,
        "reference_price": float(ref) if ref is not None else None,
        "reference_role": role,
        "thesis_holds": thesis_holds,
        "window_start_ts_ms": t0,
        "window_end_ts_ms": t1,
        "pnl_net_usdt": float(pnl),
        "side": side,
        "reasoning_accuracy_0_1": float(accuracy),
        "quality_label": label,
        "review_json": review,
        "attribution_meta_json": {
            "level_extraction": _src,
            "execution_id_resolved": str(ex_id) if ex_id else None,
            "ai_log_present": bool(log_row),
            "eval_meta": eval_meta,
        },
    }
    try:
        with conn.transaction():
            repo_post_trade_review.insert_post_trade_review(conn, row)
        logger.info(
            "ai_attribution stored eval=%s label=%s acc=%.2f",
            evaluation_id,
            label,
            accuracy,
        )
    except Exception as exc:
        logger.warning("ai_attribution insert failed eval=%s: %s", evaluation_id, exc)
