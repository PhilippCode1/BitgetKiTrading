from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import psycopg

from paper_broker.events.publisher import publish_trade_closed_evt, publish_trade_updated
from paper_broker.risk.plan_service import parse_plan_json
from paper_broker.storage import repo_position_events, repo_positions
from shared_py.exit_engine import evaluate_exit_plan

# Fach-Exit (Trailing/Wick) ist ausschliesslich in shared_py.exit_engine — hier nur I/O

if TYPE_CHECKING:
    from paper_broker.engine.broker import PaperBrokerService

logger = logging.getLogger("paper_broker.stop_tp")


def _dec(x: Any) -> Decimal:
    if x is None:
        return Decimal("0")
    return Decimal(str(x))
def run_stop_tp_for_position(
    broker: PaperBrokerService,
    conn: psycopg.Connection[Any],
    pos: dict[str, Any],
    now_ms: int,
) -> bool:
    """
    Stop/TP/Runner für eine Position auswerten.
    Returns True wenn Position vollständig geschlossen wurde (SL, Runner-Trail, oder letzter TP).
    """
    if not broker.settings.paper_stop_tp_enabled:
        return False

    pid = UUID(str(pos["position_id"]))
    sym = str(pos["symbol"])
    side = str(pos["side"])
    entry = _dec(pos["entry_price_avg"])

    mark, fill = broker.get_mark_and_fill(conn, sym)
    if mark <= 0:
        return False
    if fill <= 0:
        fill = mark

    t_str = str(pos.get("tenant_id") or broker._paper_tenant_id())  # noqa: SLF001
    pos2 = repo_positions.get_position(conn, pid, tenant_id=t_str)
    if pos2 is None or str(pos2["state"]) in ("closed", "liquidated"):
        return True

    stop_p = parse_plan_json(pos2.get("stop_plan_json"))
    tp_p = parse_plan_json(pos2.get("tp_plan_json"))
    if stop_p is None and tp_p is None:
        return False

    decision = evaluate_exit_plan(
        side=side,
        entry_price=entry,
        current_qty=_dec(pos2["qty_base"]),
        mark_price=mark,
        fill_price=fill,
        stop_plan=stop_p,
        tp_plan=tp_p,
        now_ms=now_ms,
    )
    actions = decision.get("actions") or []
    if not actions:
        return False

    for action in actions:
        if action.get("action") == "close_full":
            qty0 = _dec(pos2["qty_base"])
            if qty0 <= 0:
                return True
            reason_code = str(action.get("reason_code") or "exit")
            event_type = "SL_HIT" if reason_code == "stop_loss_hit" else "RUNNER_TRAIL_HIT"
            close_reason = "SL_HIT" if event_type == "SL_HIT" else "RUNNER_TRAIL"
            with conn.transaction():
                broker._close_qty_in_conn(  # noqa: SLF001
                    conn,
                    pid,
                    qty0,
                    "market",
                    now_ms,
                    allow_during_trading_halt=True,
                )
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type=event_type,
                    details={
                        "mark": str(mark),
                        "fill": str(fill),
                        "decision_reason": reason_code,
                        "exit_policy_version": decision.get("policy_version"),
                        "stop_price": action.get("stop_price"),
                        "trail_stop": action.get("trail_stop"),
                    },
                )
            logger.info("paper_exit_full position_id=%s reason=%s", pid, reason_code)
            publish_trade_closed_evt(
                broker.bus,
                position_id=str(pid),
                symbol=sym,
                reason=close_reason,
            )
            return True

    tp_hit_indices: list[int] = []
    did_close_partial = False
    for action in actions:
        if action.get("action") != "close_partial":
            continue
        qty_close = _dec(action.get("qty"))
        tp_index = int(action.get("tp_index") or 0)
        if qty_close <= 0:
            continue
        with conn.transaction():
            broker._close_qty_in_conn(  # noqa: SLF001
                conn,
                pid,
                qty_close,
                "market",
                now_ms,
                allow_during_trading_halt=True,
            )
            repo_position_events.insert_position_event(
                conn,
                position_id=pid,
                ts_ms=now_ms,
                event_type="TP_HIT",
                details={
                    "tp_index": tp_index,
                    "qty": str(qty_close),
                    "mark": str(mark),
                    "fill": str(fill),
                    "decision_reason": action.get("reason_code"),
                    "exit_policy_version": decision.get("policy_version"),
                },
            )
        tp_hit_indices.append(tp_index)
        did_close_partial = True
        logger.info("paper_exit_partial position_id=%s tp_index=%s", pid, tp_index)

    pos_after = repo_positions.get_position(conn, pid, tenant_id=t_str)
    if pos_after and str(pos_after["state"]) in ("open", "partially_closed"):
        updated_stop = decision.get("updated_stop_plan")
        updated_tp = decision.get("updated_tp_plan")
        with conn.transaction():
            if updated_stop is not None:
                repo_positions.update_stop_plan_only(
                    conn,
                    pid,
                    tenant_id=t_str,
                    stop_plan_json=updated_stop,
                    plan_updated_ts_ms=now_ms,
                )
            if updated_tp is not None:
                repo_positions.update_tp_plan_only(
                    conn,
                    pid,
                    tenant_id=t_str,
                    tp_plan_json=updated_tp,
                    plan_updated_ts_ms=now_ms,
                )
            if any(action.get("reason_code") == "break_even_applied" for action in actions):
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type="PLAN_UPDATED",
                    details={
                        "source": "break_even_after_tp1",
                        "exit_policy_version": decision.get("policy_version"),
                    },
                )
            for action in actions:
                if action.get("reason_code") != "trailing_updated":
                    continue
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type="TRAILING_UPDATE",
                    details={
                        "trail_stop": action.get("trail_stop"),
                        "exit_policy_version": decision.get("policy_version"),
                    },
                )

    if did_close_partial:
        pf = repo_positions.get_position(conn, pid, tenant_id=t_str)
        publish_trade_updated(
            broker.bus,
            position_id=str(pid),
            symbol=sym,
            qty_base=str(_dec(pf["qty_base"])) if pf else "0",
            state=str(pf["state"]) if pf else "unknown",
            tp_index=max(tp_hit_indices) if tp_hit_indices else None,
        )

    pos_final = repo_positions.get_position(conn, pid, tenant_id=t_str)
    return pos_final is None or str(pos_final["state"]) in ("closed", "liquidated")
