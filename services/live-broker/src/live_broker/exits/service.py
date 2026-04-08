from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from live_broker.events import publish_operator_intel
from live_broker.orders.models import OrderCreateRequest, OrderReplaceRequest, ReduceOnlyOrderRequest
from live_broker.private_rest import BitgetRestError
from shared_py.eventbus import RedisStreamBus
from shared_py.operator_intel import build_operator_intel_envelope_payload
from shared_py.exit_family_resolver import (
    extract_exit_execution_hints_from_trace,
    extract_exit_family_resolution_from_trace,
)
from shared_py.exit_engine import (
    adjust_stop_take_for_mae_mfe,
    build_exit_intent_document,
    build_live_exit_plans,
    merge_exit_build_overrides,
    evaluate_exit_plan,
    validate_exit_plan,
)

if TYPE_CHECKING:
    from live_broker.config import LiveBrokerSettings
    from live_broker.exchange_client import BitgetExchangeClient
    from live_broker.orders.service import LiveBrokerOrderService
    from live_broker.persistence.repo import LiveBrokerRepository

logger = logging.getLogger("live_broker.exits")


def _dec(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _opt_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _opt_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _trace_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trace_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _position_side_for_order(order_side: str) -> str:
    return "long" if str(order_side).lower() == "buy" else "short"


def _close_side(position_side: str) -> str:
    return "sell" if str(position_side).lower() == "long" else "buy"


def _open_side(position_side: str) -> str:
    return "buy" if str(position_side).lower() == "long" else "sell"


class LiveExitService:
    def __init__(
        self,
        settings: "LiveBrokerSettings",
        repo: "LiveBrokerRepository",
        exchange_client: "BitgetExchangeClient",
        order_service: "LiveBrokerOrderService",
    ) -> None:
        self._settings = settings
        self._repo = repo
        self._exchange_client = exchange_client
        self._order_service = order_service
        self._event_bus: RedisStreamBus | None = None

    def set_event_bus(self, bus: RedisStreamBus | None) -> None:
        self._event_bus = bus

    def preview_order_exit_plan(
        self,
        *,
        internal_order_id: str,
        request: OrderCreateRequest,
    ) -> dict[str, Any] | None:
        stop_loss = _dec(request.preset_stop_loss_price or request.trace.get("stop_loss"))
        take_profit = _dec(request.preset_stop_surplus_price or request.trace.get("take_profit"))
        if stop_loss <= 0 and take_profit <= 0:
            return None
        return self._build_plan_record(
            root_internal_order_id=internal_order_id,
            symbol=request.symbol,
            order_side=request.side,
            timeframe=_opt_text(request.trace.get("timeframe")),
            source_signal_id=_opt_text(request.trace.get("signal_id")),
            qty_base=_dec(request.size),
            entry_price=_dec(request.price or request.trace.get("entry_price")),
            stop_loss=stop_loss if stop_loss > 0 else None,
            take_profit=take_profit if take_profit > 0 else None,
            leverage=_dec(request.trace.get("leverage") or request.trace.get("signal_recommended_leverage")),
            allowed_leverage=_opt_int(
                request.trace.get("allowed_leverage")
                or request.trace.get("signal_allowed_leverage")
            ),
            risk_trade_action=_opt_text(
                (request.trace.get("risk_engine") or {}).get("trade_action")
                if isinstance(request.trace.get("risk_engine"), dict)
                else request.trace.get("signal_trade_action")
            ),
            existing_plan=None,
            last_reason="order_create_preview",
            signal_trace=dict(request.trace) if isinstance(request.trace, dict) else None,
        )

    def persist_order_exit_plan(self, *, order: dict[str, Any], preview: dict[str, Any] | None) -> None:
        if preview is None:
            return
        stored = self._repo.upsert_exit_plan(preview)
        self._audit(
            category="exit_plan",
            action="registered",
            severity="info",
            scope="trade",
            scope_key=f"order:{stored['root_internal_order_id']}",
            internal_order_id=str(stored["root_internal_order_id"]),
            symbol=stored.get("symbol"),
            details={
                "state": stored.get("state"),
                "last_reason": stored.get("last_reason"),
            },
        )

    def on_order_replaced(
        self,
        *,
        existing_order: dict[str, Any],
        new_order: dict[str, Any],
        request: OrderReplaceRequest,
    ) -> None:
        root_internal_order_id = self._order_service.trade_root_internal_order_id(
            str(existing_order["internal_order_id"])
        )
        existing_plan = self._repo.get_exit_plan_by_root_order(root_internal_order_id)
        if existing_plan is None and not any(
            (
                request.new_preset_stop_loss_price,
                request.new_preset_stop_surplus_price,
            )
        ):
            return
        context = (existing_plan or {}).get("context_json") or {}
        if not isinstance(context, dict):
            context = {}
        record = self._build_plan_record(
            root_internal_order_id=root_internal_order_id,
            symbol=str(existing_order["symbol"]),
            order_side=str(existing_order["side"]),
            timeframe=_opt_text(context.get("timeframe")),
            source_signal_id=_opt_text(context.get("source_signal_id")),
            qty_base=_dec(request.new_size or new_order.get("size")),
            entry_price=_dec(request.new_price or new_order.get("price") or context.get("entry_price")),
            stop_loss=_dec(
                request.new_preset_stop_loss_price or context.get("raw_stop_loss_price")
            )
            or None,
            take_profit=_dec(
                request.new_preset_stop_surplus_price or context.get("raw_take_profit_price")
            )
            or None,
            leverage=_dec(context.get("leverage")),
            allowed_leverage=_opt_int(context.get("allowed_leverage")),
            risk_trade_action=_opt_text(context.get("risk_trade_action")),
            existing_plan=existing_plan,
            last_reason="order_replace",
            signal_trace=context,
        )
        if record is None:
            return
        self._repo.upsert_exit_plan(record)
        self._audit(
            category="exit_plan",
            action="replace_update",
            severity="info",
            scope="trade",
            scope_key=f"order:{root_internal_order_id}",
            internal_order_id=root_internal_order_id,
            symbol=existing_order.get("symbol"),
            details={"state": record.get("state")},
        )

    def on_order_canceled(self, *, order: dict[str, Any]) -> None:
        root_internal_order_id = self._order_service.trade_root_internal_order_id(
            str(order["internal_order_id"])
        )
        existing_plan = self._repo.get_exit_plan_by_root_order(root_internal_order_id)
        if existing_plan is None or str(existing_plan.get("state")) != "pending":
            return
        updated = {
            **existing_plan,
            "state": "cancelled",
            "last_reason": "root_order_canceled_before_activation",
            "closed_ts": self._now_ts(),
        }
        self._repo.upsert_exit_plan(updated)
        self._audit(
            category="exit_plan",
            action="cancelled",
            severity="warn",
            scope="trade",
            scope_key=f"order:{root_internal_order_id}",
            internal_order_id=root_internal_order_id,
            symbol=existing_plan.get("symbol"),
            details={"state": "cancelled"},
        )

    def run_once(self, *, reason: str) -> dict[str, Any]:
        summary = {
            "plans_checked": 0,
            "plans_finalized": 0,
            "plans_closed": 0,
            "exit_orders_submitted": 0,
            "last_reason": reason,
        }
        if not self._settings.live_exits_enabled:
            summary["disabled"] = True
            return summary

        plans = self._repo.list_active_exit_plans(limit=200)
        for plan in plans:
            summary["plans_checked"] += 1
            try:
                position = self._position_snapshot(str(plan["symbol"]), str(plan["side"]))
                state = str(plan.get("state") or "pending")
                if state == "closing":
                    if position is None or position["qty"] <= 0:
                        self._close_plan(plan, reason="position_flattened_after_exit_submission")
                        summary["plans_closed"] += 1
                    continue
                if position is None or position["qty"] <= 0:
                    if state == "active":
                        self._close_plan(plan, reason="position_flattened")
                        summary["plans_closed"] += 1
                    continue
                if state == "pending":
                    finalized = self._finalize_pending_plan(plan, position)
                    if finalized:
                        summary["plans_finalized"] += 1
                    continue
                submitted = self._evaluate_active_plan(plan, position, reason=reason)
                summary["exit_orders_submitted"] += submitted
            except Exception as exc:
                logger.exception("live exit evaluation failed plan_id=%s error=%s", plan.get("plan_id"), exc)
                self._audit(
                    category="exit_plan",
                    action="evaluation_failed",
                    severity="critical",
                    scope="trade",
                    scope_key=f"order:{plan['root_internal_order_id']}",
                    internal_order_id=str(plan["root_internal_order_id"]),
                    symbol=plan.get("symbol"),
                    details={"error": str(exc)[:200]},
                )
        return summary

    def _build_plan_record(
        self,
        *,
        root_internal_order_id: str,
        symbol: str,
        order_side: str,
        timeframe: str | None,
        source_signal_id: str | None,
        qty_base: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal | None,
        take_profit: Decimal | None,
        leverage: Decimal,
        allowed_leverage: int | None,
        risk_trade_action: str | None,
        existing_plan: dict[str, Any] | None,
        last_reason: str,
        signal_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if stop_loss is None and take_profit is None:
            return None
        side = _position_side_for_order(order_side)
        context = dict((existing_plan or {}).get("context_json") or {})
        trace: dict[str, Any] = dict(signal_trace) if isinstance(signal_trace, dict) else {}
        context.update(
            {
                "source_signal_id": source_signal_id,
                "timeframe": timeframe,
                "leverage": str(leverage) if leverage > 0 else None,
                "allowed_leverage": allowed_leverage,
                "risk_trade_action": risk_trade_action,
                "raw_stop_loss_price": str(stop_loss) if stop_loss is not None else None,
                "raw_take_profit_price": str(take_profit) if take_profit is not None else None,
                "entry_price": str(entry_price) if entry_price > 0 else None,
            }
        )
        for k in (
            "expected_mae_bps",
            "expected_mfe_bps",
            "market_regime",
            "spread_bps",
            "depth_to_bar_volume_ratio",
            "mark_price",
            "fill_price",
            "exit_time_stop_deadline_ts_ms",
        ):
            if trace.get(k) is not None:
                context[k] = trace[k]
        efr = extract_exit_family_resolution_from_trace(trace)
        if efr:
            context["exit_family_resolution"] = efr
        exh = extract_exit_execution_hints_from_trace(trace)
        if exh:
            context["exit_execution_hints"] = exh
        stop_plan: dict[str, Any] = {}
        tp_plan: dict[str, Any] = {}
        state = "pending"
        last_decision: dict[str, Any] = {"stage": "preview_pending_entry"}
        if entry_price > 0 and qty_base > 0:
            adj_stop, adj_tp = stop_loss, take_profit
            adj_meta: dict[str, Any] = {}
            if any(
                trace.get(x) is not None
                for x in ("expected_mae_bps", "expected_mfe_bps", "market_regime")
            ):
                adj_stop, adj_tp, adj_meta = adjust_stop_take_for_mae_mfe(
                    side=side,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    expected_mae_bps=_trace_float(trace.get("expected_mae_bps")),
                    expected_mfe_bps=_trace_float(trace.get("expected_mfe_bps")),
                    regime=_opt_text(trace.get("market_regime")),
                    spread_bps=_trace_float(trace.get("spread_bps")),
                    depth_ratio=_trace_float(trace.get("depth_to_bar_volume_ratio")),
                )
            time_stop_ms = _opt_int(trace.get("exit_time_stop_deadline_ts_ms"))
            hints = extract_exit_execution_hints_from_trace(trace)
            ov = merge_exit_build_overrides(
                take_pcts=(
                    Decimal(str(self._settings.tp1_pct)),
                    Decimal(str(self._settings.tp2_pct)),
                    Decimal(str(self._settings.tp3_pct)),
                ),
                runner_enabled=bool(self._settings.exit_runner_enabled),
                runner_trail_mult=Decimal(str(self._settings.runner_trail_atr_mult)),
                break_even_after_tp_index=int(self._settings.exit_break_even_after_tp_index),
                hints=hints,
            )
            stop_payload, tp_payload = build_live_exit_plans(
                side=side,
                entry_price=entry_price,
                initial_qty=qty_base,
                stop_loss=adj_stop,
                take_profit=adj_tp,
                stop_trigger_type=self._settings.stop_trigger_type_default,
                tp_trigger_type=self._settings.tp_trigger_type_default,
                take_pcts=ov["take_pcts"],
                runner_enabled=ov["runner_enabled"],
                runner_trail_mult=ov["runner_trail_mult"],
                break_even_after_tp_index=ov["break_even_after_tp_index"],
                timeframe=timeframe,
                time_stop_deadline_ts_ms=time_stop_ms,
                runner_arm_after_tp_index=int(ov["runner_arm_after_tp_index"]),
            )
            mp = _dec(trace.get("mark_price"))
            fp = _dec(trace.get("fill_price"))
            validation = validate_exit_plan(
                side=side,
                entry_price=entry_price,
                stop_plan=stop_payload,
                tp_plan=tp_payload,
                leverage=leverage if leverage > 0 else None,
                allowed_leverage=allowed_leverage,
                max_position_risk_pct=self._settings.risk_max_position_risk_pct,
                risk_trade_action=risk_trade_action,
                mark_price=mp if mp > 0 else None,
                fill_price=fp if fp > 0 else None,
                market_family=str(trace.get("market_family") or self._settings.market_family),
                spread_bps=_dec(trace.get("spread_bps")) if trace.get("spread_bps") not in (None, "") else None,
                price_tick_size=_trace_decimal(
                    ((trace.get("instrument_metadata") or {}).get("entry") or {}).get("price_tick_size")
                    if isinstance((trace.get("instrument_metadata") or {}).get("entry"), dict)
                    else None
                ),
                quantity_step=_trace_decimal(
                    ((trace.get("instrument_metadata") or {}).get("entry") or {}).get("quantity_step")
                    if isinstance((trace.get("instrument_metadata") or {}).get("entry"), dict)
                    else None
                ),
                quantity_min=_trace_decimal(
                    ((trace.get("instrument_metadata") or {}).get("entry") or {}).get("quantity_min")
                    if isinstance((trace.get("instrument_metadata") or {}).get("entry"), dict)
                    else None
                ),
                quantity_max=_trace_decimal(
                    ((trace.get("instrument_metadata") or {}).get("entry") or {}).get("quantity_max")
                    if isinstance((trace.get("instrument_metadata") or {}).get("entry"), dict)
                    else None
                ),
                trading_status=_opt_text(
                    ((trace.get("instrument_metadata") or {}).get("entry") or {}).get("trading_status")
                    if isinstance((trace.get("instrument_metadata") or {}).get("entry"), dict)
                    else None
                ),
                session_trade_allowed=(
                    bool(((trace.get("instrument_metadata") or {}).get("session_state") or {}).get("trade_allowed_now"))
                    if isinstance((trace.get("instrument_metadata") or {}).get("session_state"), dict)
                    else None
                ),
                session_open_new_positions_allowed=(
                    bool(((trace.get("instrument_metadata") or {}).get("session_state") or {}).get("open_new_positions_allowed_now"))
                    if isinstance((trace.get("instrument_metadata") or {}).get("session_state"), dict)
                    else None
                ),
                catalog_snapshot_id=_opt_text((trace.get("instrument_metadata") or {}).get("snapshot_id")),
                depth_ratio=_trace_float(trace.get("depth_to_bar_volume_ratio")),
            )
            last_decision = {
                "stage": "preview_validation",
                "validation": validation,
            }
            if not validation["valid"]:
                raise BitgetRestError(
                    classification="validation",
                    message="ungueltiger Exit-Plan: " + ",".join(validation["reasons"]),
                    retryable=False,
                )
            stop_plan = validation["stop_plan"] or {}
            tp_plan = validation["tp_plan"] or {}
            state = "active"
            context["exit_intent_json"] = build_exit_intent_document(
                side=side,
                entry_price=entry_price,
                stop_loss=adj_stop,
                take_profit=adj_tp,
                adjustment_meta=adj_meta,
                expected_mae_bps=_trace_float(trace.get("expected_mae_bps")),
                expected_mfe_bps=_trace_float(trace.get("expected_mfe_bps")),
                market_regime=_opt_text(trace.get("market_regime")),
            )
        return {
            "plan_id": (existing_plan or {}).get("plan_id"),
            "root_internal_order_id": root_internal_order_id,
            "source_signal_id": source_signal_id,
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
            "state": state,
            "entry_price": str(entry_price) if entry_price > 0 else None,
            "initial_qty": str(qty_base) if qty_base > 0 else None,
            "remaining_qty": str(qty_base) if qty_base > 0 else None,
            "stop_plan_json": stop_plan,
            "tp_plan_json": tp_plan,
            "context_json": context,
            "last_market_json": (existing_plan or {}).get("last_market_json") or {},
            "last_decision_json": last_decision,
            "last_reason": last_reason,
            "closed_ts": None if state in {"pending", "active"} else self._now_ts(),
        }

    def _finalize_pending_plan(self, plan: dict[str, Any], position: dict[str, Any]) -> bool:
        context = dict(plan.get("context_json") or {})
        try:
            record = self._build_plan_record(
                root_internal_order_id=str(plan["root_internal_order_id"]),
                symbol=str(plan["symbol"]),
                order_side=_open_side(str(plan["side"])),
                timeframe=_opt_text(plan.get("timeframe")),
                source_signal_id=_opt_text(plan.get("source_signal_id")),
                qty_base=position["qty"],
                entry_price=position["entry_price"],
                stop_loss=_dec(context.get("raw_stop_loss_price")) or None,
                take_profit=_dec(context.get("raw_take_profit_price")) or None,
                leverage=_dec(context.get("leverage")),
                allowed_leverage=_opt_int(context.get("allowed_leverage")),
                risk_trade_action=_opt_text(context.get("risk_trade_action")),
                existing_plan=plan,
                last_reason="position_snapshot_activated_plan",
                signal_trace=context,
            )
        except BitgetRestError as exc:
            self._repo.upsert_exit_plan(
                {
                    **plan,
                    "state": "invalid",
                    "last_reason": str(exc),
                    "last_decision_json": {"stage": "finalize_pending_failed", "error": str(exc)},
                    "closed_ts": self._now_ts(),
                }
            )
            self._audit(
                category="exit_plan",
                action="invalid",
                severity="critical",
                scope="trade",
                scope_key=f"order:{plan['root_internal_order_id']}",
                internal_order_id=str(plan["root_internal_order_id"]),
                symbol=plan.get("symbol"),
                details={"error": str(exc)},
            )
            return False
        if record is None:
            return False
        self._repo.upsert_exit_plan(record)
        self._audit(
            category="exit_plan",
            action="activated",
            severity="info",
            scope="trade",
            scope_key=f"order:{plan['root_internal_order_id']}",
            internal_order_id=str(plan["root_internal_order_id"]),
            symbol=plan.get("symbol"),
            details={"entry_price": str(position["entry_price"]), "qty": str(position["qty"])},
        )
        return True

    def _evaluate_active_plan(
        self,
        plan: dict[str, Any],
        position: dict[str, Any],
        *,
        reason: str,
    ) -> int:
        market = self._exchange_client.get_market_snapshot(str(plan["symbol"]))
        mark_price = _dec(market.get("mark_price") or market.get("last_price"))
        if mark_price <= 0:
            return 0
        fill_price = self._close_fill_price(str(plan["side"]), market, mark_price)
        current_qty = position["qty"]
        planned_remaining = _dec(plan.get("remaining_qty"))
        if planned_remaining > 0:
            current_qty = min(current_qty, planned_remaining)
        now_ms = int(time.time() * 1000)
        decision = evaluate_exit_plan(
            side=str(plan["side"]),
            entry_price=_dec(plan.get("entry_price") or position["entry_price"]),
            current_qty=current_qty,
            mark_price=mark_price,
            fill_price=fill_price,
            stop_plan=plan.get("stop_plan_json") if isinstance(plan.get("stop_plan_json"), dict) else {},
            tp_plan=plan.get("tp_plan_json") if isinstance(plan.get("tp_plan_json"), dict) else {},
            now_ms=now_ms,
        )
        actions = list(decision.get("actions") or [])
        if not actions:
            self._repo.upsert_exit_plan(
                {
                    **plan,
                    "last_market_json": market,
                    "last_decision_json": {"reason": reason, "decision": decision},
                    "last_reason": "monitor_no_action",
                }
            )
            return 0
        submitted = 0
        remaining_qty = current_qty
        state = str(plan.get("state") or "active")
        ctx = dict(plan.get("context_json") or {})
        exec_log = list(ctx.get("execution_log_json") or [])
        for action in actions:
            if action.get("action") == "plan_update":
                continue
            exec_log.append(
                {
                    "ts_ms": now_ms,
                    "tick_reason": reason,
                    "executed_action": action,
                    "policy_version": decision.get("policy_version"),
                    "mark_price": str(mark_price),
                    "fill_price": str(fill_price),
                }
            )
            qty = _dec(action.get("qty"))
            if qty <= 0:
                continue
            self._order_service.create_reduce_only_order(
                ReduceOnlyOrderRequest(
                    source_service="live-broker",
                    symbol=str(plan["symbol"]),
                    product_type=self._settings.product_type,
                    margin_mode="isolated",
                    margin_coin=self._settings.effective_margin_coin,
                    side=_close_side(str(plan["side"])),
                    trade_side="close",
                    order_type="market",
                    size=format(qty, "f"),
                    note=f"exit:{action.get('reason_code')}",
                    trace={
                        "exit_plan_id": str(plan["plan_id"]),
                        "root_internal_order_id": str(plan["root_internal_order_id"]),
                        "reason": action.get("reason_code"),
                        "exit_policy_version": decision.get("policy_version"),
                        "trigger_price": action.get("trigger_price"),
                    },
                ),
                priority=True,
                allow_safety_bypass=True,
            )
            submitted += 1
            remaining_qty = max(Decimal("0"), remaining_qty - qty)
            if action.get("action") == "close_full" or remaining_qty <= 0:
                state = "closing"
            self._audit(
                category="exit_plan",
                action=str(action.get("reason_code") or "exit_order"),
                severity="warn",
                scope="trade",
                scope_key=f"order:{plan['root_internal_order_id']}",
                internal_order_id=str(plan["root_internal_order_id"]),
                symbol=plan.get("symbol"),
                details={
                    "qty": str(qty),
                    "trigger_price": action.get("trigger_price"),
                    "state": state,
                },
            )
        ctx["execution_log_json"] = exec_log
        updated = {
            **plan,
            "state": state,
            "remaining_qty": str(remaining_qty),
            "stop_plan_json": decision.get("updated_stop_plan") or {},
            "tp_plan_json": decision.get("updated_tp_plan") or {},
            "context_json": ctx,
            "last_market_json": market,
            "last_decision_json": {"reason": reason, "decision": decision},
            "last_reason": ",".join(decision.get("reasons") or []) or "exit_action_submitted",
            "closed_ts": self._now_ts() if state == "closed" else None,
        }
        self._repo.upsert_exit_plan(updated)
        return submitted

    def _close_fill_price(
        self,
        position_side: str,
        market: dict[str, Any],
        mark_price: Decimal,
    ) -> Decimal:
        if str(position_side).lower() == "long":
            close_price = _dec(market.get("bid_price") or market.get("last_price"))
        else:
            close_price = _dec(market.get("ask_price") or market.get("last_price"))
        return close_price if close_price > 0 else mark_price

    def _position_snapshot(self, symbol: str, side: str) -> dict[str, Decimal] | None:
        snapshots = self._repo.list_latest_exchange_snapshots("positions", symbol=symbol, limit=20)
        for snapshot in snapshots:
            raw_data = snapshot.get("raw_data")
            if not isinstance(raw_data, dict):
                continue
            items = raw_data.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                inst_id = _opt_text(item.get("instId") or item.get("symbol") or symbol)
                hold_side = _opt_text(item.get("holdSide") or item.get("side"))
                if inst_id is not None and inst_id.upper() != symbol.upper():
                    continue
                if hold_side is not None and hold_side.lower() != side.lower():
                    continue
                qty = abs(_dec(item.get("total") or item.get("size")))
                if qty <= 0:
                    continue
                entry_price = _dec(
                    item.get("openPriceAvg")
                    or item.get("avgOpenPrice")
                    or item.get("averageOpenPrice")
                    or item.get("openPrice")
                    or item.get("avgPrice")
                )
                return {"qty": qty, "entry_price": entry_price}
        return None

    def _close_plan(self, plan: dict[str, Any], *, reason: str) -> None:
        self._repo.upsert_exit_plan(
            {
                **plan,
                "state": "closed",
                "remaining_qty": "0",
                "last_reason": reason,
                "closed_ts": self._now_ts(),
            }
        )
        self._audit(
            category="exit_plan",
            action="closed",
            severity="info",
            scope="trade",
            scope_key=f"order:{plan['root_internal_order_id']}",
            internal_order_id=str(plan["root_internal_order_id"]),
            symbol=plan.get("symbol"),
            details={"reason": reason},
        )
        self._maybe_publish_exit_intel(plan, reason=reason)

    def _maybe_publish_exit_intel(self, plan: dict[str, Any], *, reason: str) -> None:
        if not self._settings.live_operator_intel_outbox_enabled or self._event_bus is None:
            return
        root = str(plan.get("root_internal_order_id") or "")
        sym = str(plan.get("symbol") or "?")
        ctx = plan.get("context_json") if isinstance(plan.get("context_json"), dict) else {}
        pl = build_operator_intel_envelope_payload(
            intel_kind="exit_result",
            symbol=sym,
            correlation_id=f"order:{root}" if root else None,
            playbook_id=str(ctx.get("playbook_id") or "")[:64] or None,
            specialist_route="exit_engine",
            outcome=str(reason)[:240],
            internal_order_id=root or None,
            severity="info",
            dedupe_key=f"opintel:exit:{root}:{reason}"[:180] if root else None,
            dedupe_ttl_minutes=30,
            notes="Exit-Plan geschlossen (deterministische Exit-Logik).",
        )
        try:
            publish_operator_intel(
                self._event_bus,
                symbol=sym,
                timeframe=str(plan.get("timeframe") or "") or None,
                payload=pl,
                trace={"source": "live-broker-exit"},
            )
        except Exception as exc:
            logger.warning("operator_intel exit publish failed: %s", exc)

    def _audit(
        self,
        *,
        category: str,
        action: str,
        severity: str,
        scope: str,
        scope_key: str,
        internal_order_id: str,
        symbol: Any,
        details: dict[str, Any],
    ) -> None:
        self._repo.record_audit_trail(
            {
                "category": category,
                "action": action,
                "severity": severity,
                "scope": scope,
                "scope_key": scope_key,
                "source": "live-exit-service",
                "internal_order_id": internal_order_id,
                "symbol": symbol,
                "details_json": details,
            }
        )

    def _now_ts(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
