from __future__ import annotations

import json
import logging
import time
from collections import deque
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

import psycopg
import psycopg.errors
from shared_py.customer_telegram_repo import is_telegram_connected
from shared_py.exit_engine import apply_break_even_update
from shared_py.risk_engine import build_trade_risk_limits, evaluate_trade_risk

from paper_broker.config import PaperBrokerSettings
from paper_broker.events.publisher import publish_risk_alert
from paper_broker.risk.common_risk import build_paper_account_risk_metrics
from paper_broker.risk.plan_service import parse_plan_json
from paper_broker.storage import (
    repo_accounts,
    repo_position_events,
    repo_positions,
    repo_signals,
    repo_strategy,
)
from paper_broker.storage.connection import paper_connect
from paper_broker.strategy.drawing_updates import maybe_update_tp_from_drawings
from paper_broker.strategy.gating import (
    GateConfig,
    should_auto_trade,
    warnung_against_position,
)
from paper_broker.strategy.news_shock import evaluate_news_shock
from paper_broker.strategy.registry import (
    is_strategy_registry_allowlisted,
    pick_strategy,
)

if TYPE_CHECKING:
    from paper_broker.engine.broker import PaperBrokerService

logger = logging.getLogger("paper_broker.strategy.engine")


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


def merge_signal_with_db(
    conn: psycopg.Connection[Any], payload: dict[str, Any]
) -> dict[str, Any]:
    out = dict(payload)
    sid = out.get("signal_id")
    if not sid:
        return out
    try:
        uid = UUID(str(sid))
    except ValueError:
        return out
    row = repo_signals.fetch_signal_v1(conn, uid)
    if not row:
        return out
    for k, v in row.items():
        if k not in out:
            out[k] = v
    return out


class StrategyExecutionEngine:
    def __init__(self, settings: PaperBrokerSettings, broker: PaperBrokerService) -> None:
        self.settings = settings
        self.broker = broker
        self._signal_ids: deque[str] = deque(maxlen=max(1, settings.strategy_signal_queue_max))

    def _state_key(self, symbol: str) -> str:
        return symbol.upper()

    def _record_no_trade_gate(
        self,
        conn: psycopg.Connection[Any],
        *,
        now_ms: int,
        symbol: str,
        payload: dict[str, Any],
        gate_code: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        repo_strategy.insert_strategy_event(
            conn,
            ts_ms=now_ms,
            event_type="NO_TRADE_GATE",
            details={
                "gate_code": gate_code,
                "symbol": symbol.upper(),
                "signal_id": str(payload.get("signal_id") or ""),
                **(extra or {}),
            },
        )

    def handle_signal_created(self, payload: dict[str, Any], symbol: str) -> None:
        if not self.settings.strategy_exec_enabled:
            return
        if self.settings.execution_mode != "paper":
            logger.info(
                "auto_trade_decision skip execution_mode=%s",
                self.settings.execution_mode,
            )
            return
        now_ms = int(time.time() * 1000)
        st: dict[str, Any] | None = None
        risk_until = 0
        merged: dict[str, Any] = {}
        strat: Any = None
        intent: Any = None
        aid: UUID | None = None
        sid = ""

        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                st = repo_strategy.get_strategy_state(conn, self._state_key(symbol))
                paused = bool(st["paused"]) if st else False
                risk_until = int(st["risk_off_until_ts_ms"] or 0) if st else 0
                if paused:
                    logger.info("auto_trade_decision skip paused symbol=%s", symbol)
                    self._record_no_trade_gate(
                        conn, now_ms=now_ms, symbol=symbol, payload=payload, gate_code="paused"
                    )
                    return
                if now_ms < risk_until:
                    logger.info(
                        "auto_trade_decision skip risk_off symbol=%s until=%s",
                        symbol,
                        risk_until,
                    )
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=payload,
                        gate_code="risk_off",
                        extra={"risk_off_until_ts_ms": risk_until},
                    )
                    return
                if self.settings.strategy_exec_mode != "auto":
                    logger.info("auto_trade_decision skip mode=%s", self.settings.strategy_exec_mode)
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=payload,
                        gate_code="exec_mode_not_auto",
                        extra={"mode": self.settings.strategy_exec_mode},
                    )
                    return

                if self.settings.strategy_require_telegram:
                    tid = (self.settings.billing_prepaid_tenant_id or "default").strip()
                    try:
                        linked = is_telegram_connected(conn, tenant_id=tid)
                    except psycopg.errors.UndefinedTable:
                        linked = False
                    if not linked:
                        logger.info(
                            "auto_trade_decision skip telegram not linked tenant=%s",
                            tid,
                        )
                        self._record_no_trade_gate(
                            conn,
                            now_ms=now_ms,
                            symbol=symbol,
                            payload=payload,
                            gate_code="telegram_not_connected",
                            extra={"tenant_id": tid},
                        )
                        return

                merged = merge_signal_with_db(conn, payload)
                sid = str(merged.get("signal_id", ""))
                if sid and sid in self._signal_ids:
                    logger.info("auto_trade_decision skip duplicate signal_id=%s", sid)
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="duplicate_signal_id",
                    )
                    return

                gate_cfg = GateConfig(
                    min_strength=self.settings.strat_min_signal_strength,
                    min_prob=float(self.settings.strat_min_probability),
                    min_risk_score=self.settings.strat_min_risk_score,
                    min_expected_return_bps=float(self.settings.strat_min_expected_return_bps),
                    max_expected_mae_bps=float(self.settings.strat_max_expected_mae_bps),
                    min_projected_rr=float(self.settings.strat_min_projected_rr),
                )
                ok, reasons = should_auto_trade(merged, gate_cfg)
                logger.info(
                    "auto_trade_decision ok=%s reasons=%s signal_id=%s",
                    ok,
                    reasons,
                    merged.get("signal_id"),
                )
                if not ok:
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="signal_gates_failed",
                        extra={"reasons": reasons},
                    )
                    return

                strat = pick_strategy(self.settings, merged)
                if not is_strategy_registry_allowlisted(
                    self.settings,
                    self.broker.promoted_strategy_names,
                    strat.name,
                ):
                    logger.info(
                        "auto_trade_decision strategy_registry_skip name=%s promoted=%s",
                        strat.name,
                        sorted(self.broker.promoted_strategy_names),
                    )
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="strategy_registry_blocked",
                        extra={
                            "strategy": strat.name,
                            "promoted": sorted(self.broker.promoted_strategy_names),
                        },
                    )
                    return
                ctx: dict[str, Any] = {}
                if not strat.should_enter(merged, ctx):
                    logger.info("auto_trade_decision strategy_skip name=%s", strat.name)
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="strategy_should_not_enter",
                        extra={"strategy": strat.name},
                    )
                    return

                open_side: str | None = None
                for p in repo_positions.list_open_positions(conn):
                    if str(p["symbol"]).upper() == symbol.upper():
                        open_side = str(p["side"]).lower()
                        break
                if warnung_against_position(merged, open_side):
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="warnung_against_open",
                        extra={"open_side": open_side},
                    )
                    self._de_risk_warnung(conn, symbol, now_ms)
                    return

                aid = self._resolve_account_id(conn)
                if aid is None:
                    logger.warning("auto_trade_decision no_account")
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="no_account",
                    )
                    return

                account_row = repo_accounts.get_account(conn, aid)
                if account_row is None:
                    logger.warning("auto_trade_decision account_missing account_id=%s", aid)
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="account_row_missing",
                        extra={"account_id": str(aid)},
                    )
                    return

                ref_px = merged.get("entry_price") or merged.get("last_price")
                ctx = {
                    "account_equity": str(account_row["equity"]),
                    "reference_price": str(ref_px) if ref_px not in (None, "") else None,
                }
                intent = strat.build_order_intent(merged, ctx)
                if intent.side not in ("long", "short"):
                    self._record_no_trade_gate(
                        conn,
                        now_ms=now_ms,
                        symbol=symbol,
                        payload=merged,
                        gate_code="invalid_intent_side",
                        extra={"strategy": strat.name},
                    )
                    return
                account_metrics = build_paper_account_risk_metrics(
                    conn,
                    account_id=aid,
                    account_row=account_row,
                    now_ms=now_ms,
                )
                risk_decision = evaluate_trade_risk(
                    signal=merged,
                    limits=build_trade_risk_limits(self.settings),
                    open_positions_count=account_metrics["open_positions_count"],
                    account_drawdown_pct=account_metrics["account_drawdown_pct"],
                    daily_drawdown_pct=account_metrics["daily_drawdown_pct"],
                    weekly_drawdown_pct=account_metrics["weekly_drawdown_pct"],
                    daily_loss_usdt=account_metrics["daily_loss_usdt"],
                    signal_allowed_leverage=merged.get("allowed_leverage"),
                    signal_recommended_leverage=merged.get("recommended_leverage"),
                    leverage_cap_reasons_json=merged.get("leverage_cap_reasons_json") or [],
                )
                if risk_decision["trade_action"] == "do_not_trade":
                    logger.info(
                        "auto_trade_decision shared_risk_block reason=%s signal_id=%s",
                        risk_decision["decision_reason"],
                        merged.get("signal_id"),
                    )
                    repo_strategy.insert_strategy_event(
                        conn,
                        ts_ms=now_ms,
                        event_type="AUTO_BLOCKED",
                        details={
                            "signal_id": str(merged.get("signal_id")),
                            "strategy": strat.name,
                            "reason": risk_decision["decision_reason"],
                            "risk_decision": risk_decision,
                        },
                    )
                    return

        tf = str(merged.get("timeframe") or "5m")
        try:
            out = self.broker.open_position(
                account_id=aid,
                symbol=symbol,
                side=intent.side,
                qty_base=intent.qty_base,
                leverage=intent.leverage,
                margin_mode=self.settings.paper_default_margin_mode,
                order_type=intent.entry_type,
                ts_ms=now_ms,
                timeframe=tf,
                signal_payload=merged,
            )
        except ValueError as exc:
            logger.warning("auto_open_position failed: %s", exc)
            with paper_connect(self.settings.database_url) as conn:
                with conn.transaction():
                    repo_strategy.insert_strategy_event(
                        conn,
                        ts_ms=now_ms,
                        event_type="AUTO_BLOCKED",
                        details={
                            "signal_id": str(merged.get("signal_id")),
                            "strategy": strat.name if strat is not None else None,
                            "reason": str(exc),
                            "requested_leverage": str(intent.leverage),
                        },
                    )
            return

        pid = UUID(str(out["position_id"]))
        plan_res = self.broker.plan_auto(
            pid,
            timeframe=tf,
            preferred_trigger_type=self.settings.stop_trigger_type_default,
            method_mix=None,
        )

        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                row = repo_positions.get_position(conn, pid)
                if row is None:
                    return
                meta = _meta_dict(row["meta"])
                meta["strategy_name"] = strat.name
                meta["strategy_signal_id"] = str(merged.get("signal_id"))
                meta["plan_timeframe"] = tf
                repo_positions.update_position_meta(conn, pid, meta=meta, updated_ts_ms=now_ms)

                repo_strategy.upsert_strategy_state(
                    conn,
                    key=self._state_key(symbol),
                    paused=bool(st["paused"]) if st else False,
                    risk_off_until_ts_ms=risk_until,
                    last_signal_id=UUID(str(merged["signal_id"]))
                    if merged.get("signal_id")
                    else None,
                    updated_ts_ms=now_ms,
                )
                repo_strategy.insert_strategy_event(
                    conn,
                    ts_ms=now_ms,
                    event_type="AUTO_OPEN",
                    details={
                        "signal_id": str(merged.get("signal_id")),
                        "strategy": strat.name,
                        "position_id": str(pid),
                    },
                )
                repo_strategy.insert_strategy_event(
                    conn,
                    ts_ms=now_ms,
                    event_type="PLAN_SNAPSHOT",
                    details={
                        "signal_id": str(merged.get("signal_id")),
                        "position_id": str(pid),
                        "plan_version": plan_res.get("plan_version"),
                        "stop_plan_keys": list((plan_res.get("stop_plan") or {}).keys()),
                        "tp_plan_keys": list((plan_res.get("tp_plan") or {}).keys()),
                        "stop_quality_score": plan_res.get("stop_quality_score"),
                        "rr_estimate": plan_res.get("rr_estimate"),
                    },
                )

        if sid:
            self._signal_ids.append(sid)
        logger.info(
            "auto_open_position signal_id=%s strategy_name=%s position_id=%s",
            merged.get("signal_id"),
            strat.name,
            out["position_id"],
        )

    def _de_risk_warnung(self, conn: psycopg.Connection[Any], symbol: str, now_ms: int) -> None:
        pct = Decimal(str(self.settings.close_partial_on_news_shock_pct))
        closed: list[UUID] = []
        for pos in repo_positions.list_open_positions(conn):
            if str(pos["symbol"]).upper() != symbol.upper():
                continue
            pid = UUID(str(pos["position_id"]))
            qty = _dec(pos["qty_base"])
            if qty <= 0:
                continue
            q_close = qty * pct if pct < Decimal("1") else qty
            q_close = min(q_close, qty)
            if q_close <= 0:
                continue
            self.broker.close_position(pid, q_close, "market", ts_ms=now_ms)
            closed.append(pid)
        if not closed:
            return
        with paper_connect(self.settings.database_url) as c2:
            with c2.transaction():
                for pid in closed:
                    repo_strategy.insert_strategy_event(
                        c2,
                        ts_ms=now_ms,
                        event_type="AUTO_CLOSE",
                        details={"reason": "warnung_against", "position_id": str(pid)},
                    )

    def _resolve_account_id(self, conn: psycopg.Connection[Any]) -> UUID | None:
        raw = self.settings.strategy_default_account_id
        if raw:
            try:
                return UUID(str(raw).strip())
            except ValueError:
                return None
        return repo_accounts.first_account_id(conn)

    def handle_news_scored(self, payload: dict[str, Any], symbol: str) -> None:
        if not self.settings.strategy_exec_enabled:
            return
        now_ms = int(time.time() * 1000)
        rel = int(payload.get("relevance_score") or 0)
        sent = str(payload.get("sentiment") or "")
        iw = str(payload.get("impact_window") or "")
        pct = Decimal(str(self.settings.close_partial_on_news_shock_pct))
        thresh = self.settings.news_shock_score
        with paper_connect(self.settings.database_url) as conn:
            for pos in repo_positions.list_open_positions(conn):
                if str(pos["symbol"]).upper() != symbol.upper():
                    continue
                side = str(pos["side"]).lower()
                hit, action, _why = evaluate_news_shock(
                    relevance_score=rel,
                    sentiment=sent,
                    impact_window=iw,
                    position_side=side,
                    shock_threshold=thresh,
                    partial_pct=pct,
                )
                if not hit:
                    continue
                pid = UUID(str(pos["position_id"]))
                qty = _dec(pos["qty_base"])
                logger.info(
                    "news_shock_triggered position_id=%s action=%s relevance=%s",
                    pid,
                    action,
                    rel,
                )
                cd_ms = self.settings.news_cooldown_sec * 1000
                with conn.transaction():
                    repo_strategy.set_risk_off_until(
                        conn, self._state_key(symbol), now_ms + cd_ms, now_ms
                    )
                    repo_strategy.insert_strategy_event(
                        conn,
                        ts_ms=now_ms,
                        event_type="NEWS_SHOCK",
                        details={
                            "position_id": str(pid),
                            "action": action,
                            "relevance_score": rel,
                            "sentiment": sent,
                        },
                    )
                publish_risk_alert(
                    self.broker.bus,
                    symbol=symbol,
                    position_id=str(pid),
                    warnings=["news_shock"],
                    stop_quality_score=0,
                )
                if action == "full":
                    self.broker.close_position(pid, qty, "market", ts_ms=now_ms)
                elif action == "partial" and qty > 0:
                    q = min(qty * pct, qty)
                    if q > 0:
                        self.broker.close_position(pid, q, "market", ts_ms=now_ms)

    def handle_drawing_updated(self, payload: dict[str, Any], symbol: str, timeframe: str) -> None:
        if not self.settings.strategy_exec_enabled:
            return
        pids = payload.get("parent_ids") or []
        if not isinstance(pids, list):
            return
        ids = [str(x) for x in pids]
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                n = maybe_update_tp_from_drawings(
                    conn,
                    settings=self.settings,
                    symbol=symbol,
                    timeframe=timeframe,
                    parent_ids=ids,
                    now_ms=now_ms,
                )
            if n > 0:
                with conn.transaction():
                    repo_strategy.insert_strategy_event(
                        conn,
                        ts_ms=now_ms,
                        event_type="DRAWING_TP_UPDATE",
                        details={"parent_ids": ids, "updated_positions": n},
                    )

    def handle_structure_updated(self, payload: dict[str, Any], symbol: str, timeframe: str) -> None:
        if not self.settings.strategy_exec_enabled or not self.settings.use_structure_flip_exit:
            return
        td = str(payload.get("trend_dir", ""))
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            for pos in repo_positions.list_open_positions(conn):
                if str(pos["symbol"]).upper() != symbol.upper():
                    continue
                meta = _meta_dict(pos.get("meta"))
                ptf = str(meta.get("plan_timeframe") or timeframe)
                if ptf.lower() != timeframe.lower():
                    continue
                side = str(pos["side"]).lower()
                contradict = (side == "long" and td == "-1") or (side == "short" and td == "1")
                if not contradict:
                    continue
                pid = UUID(str(pos["position_id"]))
                if self.settings.structure_flip_full_close:
                    qty = _dec(pos["qty_base"])
                    self.broker.close_position(pid, qty, "market", ts_ms=now_ms)
                    with conn.transaction():
                        repo_strategy.insert_strategy_event(
                            conn,
                            ts_ms=now_ms,
                            event_type="STRUCTURE_FLIP_EXIT",
                            details={"position_id": str(pid), "mode": "full"},
                        )
                    logger.info("structure_flip_exit full position_id=%s", pid)
                    continue
                stop_p = parse_plan_json(pos.get("stop_plan_json"))
                if not stop_p:
                    continue
                entry = _dec(pos["entry_price_avg"])
                try:
                    sp = _dec(stop_p["stop_price"])
                except Exception:
                    continue
                tighten = _dec(pos["entry_price_avg"]) * Decimal(
                    str(self.settings.structure_flip_tighten_bps)
                ) / Decimal("10000")
                if side == "long":
                    new_stop = sp + tighten
                    if new_stop > entry:
                        new_stop = entry
                else:
                    new_stop = sp - tighten
                    if new_stop < entry:
                        new_stop = entry
                if new_stop == sp:
                    continue
                stop_p["stop_price"] = str(new_stop)
                with conn.transaction():
                    repo_positions.update_stop_plan_only(
                        conn, pid, stop_plan_json=stop_p, plan_updated_ts_ms=now_ms
                    )
                    repo_position_events.insert_position_event(
                        conn,
                        position_id=pid,
                        ts_ms=now_ms,
                        event_type="PLAN_UPDATED",
                        details={"source": "structure_flip_tighten", "trend_dir": td},
                    )
                    repo_strategy.insert_strategy_event(
                        conn,
                        ts_ms=now_ms,
                        event_type="STRUCTURE_FLIP_EXIT",
                        details={"position_id": str(pid), "mode": "tighten"},
                    )
                logger.info("structure_flip_exit tighten position_id=%s", pid)

    def run_after_market_tick(self, conn: psycopg.Connection[Any], now_ms: int) -> None:
        if not self.settings.strategy_exec_enabled:
            return
        self._apply_break_even_stops(conn, now_ms)

    def _apply_break_even_stops(self, conn: psycopg.Connection[Any], now_ms: int) -> None:
        for pos in repo_positions.list_open_positions(conn):
            meta = _meta_dict(pos.get("meta"))
            if meta.get("break_even_stop_applied"):
                continue
            tp_p = parse_plan_json(pos.get("tp_plan_json"))
            stop_p = parse_plan_json(pos.get("stop_plan_json"))
            if not tp_p or not stop_p:
                continue
            pid = UUID(str(pos["position_id"]))
            side = str(pos["side"]).lower()
            entry = _dec(pos["entry_price_avg"])
            next_stop, next_tp, changed = apply_break_even_update(
                side=side,
                entry_price=entry,
                stop_plan=stop_p,
                tp_plan=tp_p,
            )
            if next_stop is None or next_tp is None:
                continue
            if not changed:
                meta["break_even_stop_applied"] = True
                repo_positions.update_position_meta(conn, pid, meta=meta, updated_ts_ms=now_ms)
                continue
            with conn.transaction():
                repo_positions.update_stop_plan_only(
                    conn, pid, stop_plan_json=next_stop, plan_updated_ts_ms=now_ms
                )
                repo_positions.update_tp_plan_only(
                    conn, pid, tp_plan_json=next_tp, plan_updated_ts_ms=now_ms
                )
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type="PLAN_UPDATED",
                    details={"source": "break_even_after_tp1"},
                )
            meta["break_even_stop_applied"] = True
            repo_positions.update_position_meta(conn, pid, meta=meta, updated_ts_ms=now_ms)
            logger.info("break_even_stop_applied position_id=%s", pid)

    def strategy_status(self, symbol: str) -> dict[str, Any]:
        key = self._state_key(symbol)
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url, autocommit=True) as conn:
            st = repo_strategy.get_strategy_state(conn, key)
        risk_until = int(st["risk_off_until_ts_ms"] or 0) if st else 0
        return {
            "symbol": key,
            "execution_mode": self.settings.execution_mode,
            "paper_path_active": self.settings.paper_path_active,
            "strategy_exec_enabled": self.settings.strategy_exec_enabled,
            "strategy_exec_mode": self.settings.strategy_exec_mode,
            "paused": bool(st["paused"]) if st else False,
            "risk_off_until_ts_ms": risk_until,
            "risk_off_active": now_ms < risk_until,
            "last_signal_id": str(st["last_signal_id"]) if st and st.get("last_signal_id") else None,
        }

    def strategy_pause(self, symbol: str) -> None:
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                repo_strategy.set_strategy_paused(conn, self._state_key(symbol), True, now_ms)

    def strategy_resume(self, symbol: str) -> None:
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                repo_strategy.set_strategy_paused(conn, self._state_key(symbol), False, now_ms)

    def strategy_rules(self) -> dict[str, Any]:
        return {
            "STRATEGY_EXEC_ENABLED": self.settings.strategy_exec_enabled,
            "EXECUTION_MODE": self.settings.execution_mode,
            "STRATEGY_EXEC_MODE": self.settings.strategy_exec_mode,
            "RISK_MIN_SIGNAL_STRENGTH": self.settings.risk_min_signal_strength,
            "RISK_MIN_PROBABILITY": self.settings.risk_min_probability,
            "RISK_MIN_RISK_SCORE": self.settings.risk_min_risk_score,
            "RISK_MIN_EXPECTED_RETURN_BPS": self.settings.risk_min_expected_return_bps,
            "RISK_MAX_EXPECTED_MAE_BPS": self.settings.risk_max_expected_mae_bps,
            "RISK_MIN_PROJECTED_RR": self.settings.risk_min_projected_rr,
            "STRAT_BASE_QTY_BTC": self.settings.strat_base_qty_btc,
            "MICRO_SIZE_MULT": self.settings.micro_size_mult,
            "GROSS_SIZE_MULT": self.settings.gross_size_mult,
            "RISK_MAX_CONCURRENT_POSITIONS": self.settings.risk_max_concurrent_positions,
            "NEWS_SHOCK_SCORE": self.settings.news_shock_score,
            "NEWS_COOLDOWN_SEC": self.settings.news_cooldown_sec,
            "CLOSE_PARTIAL_ON_NEWS_SHOCK_PCT": self.settings.close_partial_on_news_shock_pct,
            "USE_DRAWING_TARGET_UPDATES": self.settings.use_drawing_target_updates,
            "USE_STRUCTURE_FLIP_EXIT": self.settings.use_structure_flip_exit,
            "STRUCTURE_FLIP_FULL_CLOSE": self.settings.structure_flip_full_close,
            "STRUCTURE_FLIP_TIGHTEN_BPS": self.settings.structure_flip_tighten_bps,
        }
