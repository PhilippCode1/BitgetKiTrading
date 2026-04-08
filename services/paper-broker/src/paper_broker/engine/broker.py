from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
import psycopg.errors
from shared_py.billing_wallet import fetch_prepaid_balance_list_usd, prepaid_allows_new_trade
from shared_py.customer_telegram_notify import enqueue_customer_notify
from shared_py.bitget import BitgetInstrumentCatalog
from shared_py.eventbus import EventEnvelope, RedisStreamBus
from shared_py.exit_engine import merge_plan_override, validate_exit_plan
from shared_py.risk_engine import (
    build_trade_risk_limits,
    compute_position_risk_pct,
    evaluate_trade_risk,
)

from paper_broker.config import PaperBrokerSettings
from paper_broker.engine.broker_stop_tp import run_stop_tp_for_position
from paper_broker.engine.contract_config import ContractConfigProvider
from paper_broker.engine.fees import calc_transaction_fee_usdt, order_notional_usdt
from paper_broker.engine.funding import calc_funding_usdt
from paper_broker.engine.instrument_context import (
    execution_context_for_position,
    instrument_hints_from_signal,
)
from paper_broker.engine.liquidation import should_liquidate_approx
from paper_broker.engine.pricing import (
    fetch_bitget_symbol_price,
    latest_ticker_prices,
    load_orderbook_levels,
)
from paper_broker.engine.slippage import (
    apply_slippage_bps,
    synthetic_depth_from_best,
    walk_asks_fill,
    walk_bids_fill,
)
from paper_broker.events.publisher import (
    publish_funding_booked,
    publish_risk_alert,
    publish_trade_closed_evt,
    publish_trade_opened,
    publish_trade_updated,
)
from paper_broker.risk.common_risk import build_paper_account_risk_metrics
from paper_broker.risk.leverage_allocator import allocate_paper_execution_leverage
from paper_broker.risk.plan_service import build_auto_plan_bundle, parse_plan_json
from paper_broker.storage import (
    repo_accounts,
    repo_ledgers,
    repo_orders,
    repo_position_events,
    repo_positions,
    repo_strategy,
)
from paper_broker.storage.connection import paper_connect

logger = logging.getLogger("paper_broker.engine")


def _contract_payload_from_position_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    ex = meta.get("execution_context")
    return ex if isinstance(ex, dict) and ex else None


def _meta_dict(m: Any) -> dict[str, Any]:
    if m is None:
        return {}
    if isinstance(m, dict):
        return dict(m)
    if isinstance(m, str):
        return json.loads(m) if m else {}
    return {}


def _dec(x: Any) -> Decimal:
    if x is None:
        return Decimal("0")
    return Decimal(str(x))


@dataclass
class SimMarketState:
    ts_ms: int = 0
    best_bid: Decimal = Decimal("0")
    best_ask: Decimal = Decimal("0")
    last_price: Decimal = Decimal("0")
    mark_price: Decimal = Decimal("0")


@dataclass
class SimFundingState:
    funding_rate: Decimal = Decimal("0")
    funding_interval_hours: int = 8
    next_update_ms: int = 0


@dataclass
class PaperBrokerService:
    settings: PaperBrokerSettings
    bus: RedisStreamBus
    catalog: BitgetInstrumentCatalog | None = None
    contract_provider: ContractConfigProvider = field(init=False)
    sim_market: SimMarketState | None = None
    sim_funding: SimFundingState | None = None
    strategy_engine: Any | None = None
    _tick_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    promoted_strategy_names: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.contract_provider = ContractConfigProvider(self.settings, catalog=self.catalog)

    def set_sim_market(self, st: SimMarketState) -> None:
        self.sim_market = st

    def set_sim_funding(self, st: SimFundingState) -> None:
        self.sim_funding = st

    def apply_registry_envelope(self, env: EventEnvelope) -> None:
        if env.event_type != "strategy_registry_updated":
            return
        raw = env.payload.get("promoted_strategy_names")
        if not isinstance(raw, list):
            logger.warning("strategy_registry payload ohne promoted_strategy_names list")
            return
        self.promoted_strategy_names = {str(x) for x in raw if x is not None}
        logger.info(
            "strategy_registry snapshot promoted_count=%s",
            len(self.promoted_strategy_names),
        )

    def apply_envelope_tick(self, env: EventEnvelope) -> None:
        sym = env.symbol.upper()
        pl = env.payload
        self._tick_cache[sym] = dict(pl)

    def apply_envelope_funding(self, env: EventEnvelope) -> None:
        pl = env.payload
        fr = _dec(pl.get("funding_rate") or pl.get("fundingRate"))
        nu = pl.get("funding_next_update_ms") or pl.get("nextUpdate") or pl.get("next_funding_time_ms")
        iv = pl.get("funding_rate_interval") or pl.get("fundingRateInterval")
        hours = 8
        if iv is not None:
            try:
                hours = int(Decimal(str(iv)))
            except Exception:
                hours = 8
        nu_int = int(nu) if nu is not None else int(time.time() * 1000) + hours * 3600_000
        if self.sim_funding is None:
            self.sim_funding = SimFundingState()
        self.sim_funding.funding_rate = fr
        self.sim_funding.funding_interval_hours = hours
        self.sim_funding.next_update_ms = nu_int

    def get_mark_and_bid_ask(
        self, conn: psycopg.Connection[Any], symbol: str
    ) -> tuple[Decimal, Decimal | None, Decimal | None]:
        if self.settings.paper_sim_mode and self.sim_market is not None:
            m = self.sim_market.mark_price or self.sim_market.last_price
            return m, self.sim_market.best_bid, self.sim_market.best_ask
        cached = self._tick_cache.get(symbol.upper())
        if cached:
            mark = _dec(cached.get("mark_price")) or _dec(cached.get("last_pr"))
            bid = _dec(cached.get("bid_pr")) if cached.get("bid_pr") else None
            ask = _dec(cached.get("ask_pr")) if cached.get("ask_pr") else None
            if mark > 0:
                return mark, bid, ask
        tick = latest_ticker_prices(conn, symbol)
        if tick.get("mark_price"):
            return tick["mark_price"], tick.get("bid_pr"), tick.get("ask_pr")
        rest = fetch_bitget_symbol_price(self.settings, symbol)
        m = rest.get("mark_price") or rest.get("last_pr") or Decimal("0")
        return m, rest.get("bid_pr"), rest.get("ask_pr")

    def get_mark_and_fill(self, conn: psycopg.Connection[Any], symbol: str) -> tuple[Decimal, Decimal]:
        """Mark-Preis und Fill-Proxy (last / last_pr), Bitget-Semantik für Trigger."""
        mark, bid, ask = self.get_mark_and_bid_ask(conn, symbol)
        if self.settings.paper_sim_mode and self.sim_market is not None:
            lp = self.sim_market.last_price
            fill = lp if lp and lp > 0 else mark
            return mark, fill if fill > 0 else mark
        cached = self._tick_cache.get(symbol.upper())
        if cached:
            fill = _dec(cached.get("last_pr") or cached.get("last_price") or cached.get("price"))
            if fill <= 0:
                fill = _dec(cached.get("mark_price")) or mark
            return mark, fill if fill > 0 else mark
        tick = latest_ticker_prices(conn, symbol)
        fill = tick.get("last_pr") or tick.get("mark_price") or mark
        if fill is None or fill <= 0:
            fill = mark
        return mark, fill

    def _fill_price_market(
        self,
        conn: psycopg.Connection[Any],
        symbol: str,
        order_side: str,
        qty: Decimal,
        cfg_price_step: Decimal,
    ) -> tuple[Decimal, str]:
        """order_side: buy oder sell (Execution)."""
        mark, bid, ask = self.get_mark_and_bid_ask(conn, symbol)
        levels = self.settings.paper_orderbook_levels
        ob = load_orderbook_levels(conn, symbol, None, levels)
        if ob is not None:
            bids, asks = ob
            if order_side == "buy":
                avg, filled, ok = walk_asks_fill(asks, qty)
            else:
                avg, filled, ok = walk_bids_fill(bids, qty)
            if ok and filled > 0:
                return avg, "taker"
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            qpl = max(qty, qty * Decimal("2"))
            if order_side == "buy":
                synth = synthetic_depth_from_best(
                    best_bid=bid,
                    best_ask=ask,
                    levels=levels,
                    qty_per_level=qpl,
                    price_step=cfg_price_step,
                    side_for_fill="buy",
                )
                avg, filled, ok = walk_asks_fill(synth, qty)
            else:
                synth = synthetic_depth_from_best(
                    best_bid=bid,
                    best_ask=ask,
                    levels=levels,
                    qty_per_level=qpl,
                    price_step=cfg_price_step,
                    side_for_fill="sell",
                )
                avg, filled, ok = walk_bids_fill(synth, qty)
            if ok and filled > 0:
                return avg, "taker"
        bps = Decimal(self.settings.paper_default_slippage_bps)
        ref = mark if mark > 0 else (ask if order_side == "buy" else bid) or Decimal("1")
        px = apply_slippage_bps(ref, bps, "buy" if order_side == "buy" else "sell")
        return px, "taker"

    def _close_qty_in_conn(
        self,
        conn: psycopg.Connection[Any],
        position_id: UUID,
        qty_base: Decimal,
        order_type: str,
        now_ms: int,
    ) -> dict[str, Any]:
        """Schließt qty innerhalb einer bestehenden DB-Transaktion (Partial oder Full)."""
        pos = repo_positions.get_position(conn, position_id)
        if pos is None:
            raise ValueError("position not found")
        if pos["state"] in ("closed", "liquidated"):
            raise ValueError("position already closed")
        qty0 = _dec(pos["qty_base"])
        if qty_base <= 0 or qty_base > qty0:
            raise ValueError("invalid close qty")
        symbol = str(pos["symbol"])
        side = str(pos["side"])
        entry = _dec(pos["entry_price_avg"])
        iso = _dec(pos["isolated_margin"])
        account_id = UUID(str(pos["account_id"]))
        acc = repo_accounts.get_account(conn, account_id)
        if acc is None:
            raise ValueError("account missing")
        equity = _dec(acc["equity"])
        meta0 = json.loads(pos["meta"]) if isinstance(pos["meta"], str) else (pos["meta"] or {})
        cfg = self.contract_provider.get(
            symbol,
            conn,
            signal_payload=_contract_payload_from_position_meta(meta0),
        )
        maker_r, taker_r = self.contract_provider.effective_fees(cfg)
        exec_side = "sell" if side == "long" else "buy"
        fill_px, liq = self._fill_price_market(
            conn, symbol, exec_side, qty_base, cfg.price_end_step
        )
        fee_rate = taker_r if order_type == "market" else maker_r
        notional = order_notional_usdt(qty_base, fill_px)
        fee = calc_transaction_fee_usdt(qty_base, fill_px, fee_rate)
        if side == "long":
            realized = (fill_px - entry) * qty_base
        else:
            realized = (entry - fill_px) * qty_base
        margin_release = iso * (qty_base / qty0)
        new_qty = qty0 - qty_base
        new_iso = iso - margin_release
        oid = repo_orders.insert_order(
            conn,
            position_id=position_id,
            otype=order_type,
            side=exec_side,
            qty_base=qty_base,
            limit_price=None,
            state="filled",
            created_ts_ms=now_ms,
            filled_ts_ms=now_ms,
        )
        repo_ledgers.insert_fill(
            conn,
            order_id=oid,
            position_id=position_id,
            ts_ms=now_ms,
            price=fill_px,
            qty_base=qty_base,
            liquidity=liq,
            fee_usdt=fee,
            notional_usdt=notional,
        )
        repo_ledgers.insert_fee_ledger(
            conn,
            position_id=position_id,
            ts_ms=now_ms,
            fee_usdt=fee,
            reason="partial_exit" if new_qty > 0 else "exit",
        )
        new_eq = equity + margin_release + realized - fee
        repo_accounts.update_account_equity(conn, account_id, new_eq)
        st = "partially_closed" if new_qty > 0 else "closed"
        meta = meta0
        repo_positions.update_position_qty_state(
            conn,
            position_id,
            qty_base=new_qty,
            entry_price_avg=entry,
            isolated_margin=new_iso,
            state=st,
            updated_ts_ms=now_ms,
            closed_ts_ms=None if new_qty > 0 else now_ms,
            meta=meta,
        )
        post_metrics = build_paper_account_risk_metrics(
            conn,
            account_id=account_id,
            account_row={**acc, "equity": str(new_eq)},
            now_ms=now_ms,
        )
        repo_position_events.insert_position_event(
            conn,
            position_id=position_id,
            ts_ms=now_ms,
            event_type="POSITION_REDUCED" if new_qty > 0 else "POSITION_CLOSED",
            details={
                "account_equity_after": str(new_eq),
                "account_total_equity_after": str(post_metrics["total_equity"]),
                "used_margin_after": str(post_metrics["used_margin"]),
                "realized_pnl": str(realized),
                "fee_usdt": str(fee),
                "closed_qty": str(qty_base),
            },
        )
        if new_qty == 0:
            repo_strategy.insert_strategy_event(
                conn,
                ts_ms=now_ms,
                event_type="POST_TRADE_REVIEW_READY",
                details={
                    "position_id": str(position_id),
                    "signal_id": str(
                        meta.get("strategy_signal_id") or meta.get("signal_id") or ""
                    ),
                    "realized_pnl_fill_usdt": str(realized),
                    "fee_exit_usdt": str(fee),
                    "notional_usdt": str(notional),
                },
            )
        logger.info(
            "closed partial position_id=%s fee_usdt=%s notional_usdt=%s",
            position_id,
            fee,
            notional,
        )
        tid_notify = (self.settings.billing_prepaid_tenant_id or "default").strip()
        cat = "paper_order_partial" if new_qty > 0 else "paper_order_close"
        try:
            enqueue_customer_notify(
                conn,
                tenant_id=tid_notify,
                text=(
                    f"Demo-Trade ({cat}): {symbol} reduziert/geschlossen "
                    f"Menge={qty_base} @ {fill_px} realisiert≈{realized} USDT"
                )[:3500],
                category=cat,
                severity="info",
                dedupe_key=f"{cat}:{position_id}:{now_ms}",
                audit_actor="paper_broker",
            )
        except Exception:
            logger.debug("paper close customer notify skipped", exc_info=True)
        return {
            "fill_price": fill_px,
            "fee_usdt": fee,
            "notional_usdt": notional,
            "realized_pnl": realized,
            "new_qty": new_qty,
            "state": st,
            "symbol": symbol,
            "account_equity_after": new_eq,
            "closed_qty": qty_base,
        }

    def bootstrap_account(self, initial_equity: Decimal) -> UUID:
        with paper_connect(self.settings.database_url, autocommit=True) as conn:
            aid = repo_accounts.bootstrap_account(conn, initial_equity=initial_equity)
        return aid

    def open_position(
        self,
        *,
        account_id: UUID,
        symbol: str,
        side: str,
        qty_base: Decimal,
        leverage: Decimal,
        margin_mode: str,
        order_type: str,
        ts_ms: int | None = None,
        timeframe: str | None = None,
        signal_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now_ms = ts_ms if ts_ms is not None else int(time.time() * 1000)
        symbol = symbol.upper()
        s = side.lower()
        if s not in ("long", "short"):
            raise ValueError("side muss long oder short sein")
        exec_side = "buy" if s == "long" else "sell"
        with psycopg.connect(self.settings.database_url) as conn:
            with conn.transaction():
                acc = repo_accounts.get_account(conn, account_id)
                if acc is None:
                    raise ValueError("account not found")
                if self.settings.billing_prepaid_gate_enabled:
                    tid = (self.settings.billing_prepaid_tenant_id or "default").strip()
                    min_act = _dec(self.settings.billing_min_balance_new_trade_usd)
                    bal = fetch_prepaid_balance_list_usd(conn, tenant_id=tid)
                    ok, pmsg = prepaid_allows_new_trade(
                        bal, min_activation_usd=min_act
                    )
                    if not ok:
                        try:
                            enqueue_customer_notify(
                                conn,
                                tenant_id=tid,
                                text=(
                                    "Neue Trades blockiert: Das Prepaid-Guthaben reicht fuer keine neue "
                                    f"Position. ({pmsg}) Bitte im Kundenbereich aufladen."
                                )[:3500],
                                category="trades_blocked",
                                severity="warning",
                                dedupe_key=f"trades_blocked_prepaid:{tid}",
                                audit_actor="paper_broker",
                            )
                        except psycopg.errors.UndefinedTable:
                            pass
                        raise ValueError(pmsg)
                equity = _dec(acc["equity"])
                hints = instrument_hints_from_signal(signal_payload)
                mf_d = hints.get("market_family") or str(
                    self.settings.bitget_market_family
                ).lower()
                pt_d = hints.get("product_type")
                if pt_d is None and mf_d == "futures":
                    pt_d = str(self.settings.bitget_product_type).strip().upper() or None
                mm_d = hints.get("margin_account_mode")
                if mm_d is None and mf_d == "margin":
                    mm_d = str(self.settings.bitget_margin_account_mode).lower()
                if self.catalog is not None and self.settings.paper_require_catalog_tradeable:
                    self.catalog.resolve_for_trading(
                        symbol=symbol,
                        market_family=mf_d,
                        product_type=pt_d,
                        margin_account_mode=mm_d,
                        refresh_if_missing=False,
                    )
                cfg = self.contract_provider.get(
                    symbol, conn, signal_payload=signal_payload
                )
                maker_r, taker_r = self.contract_provider.effective_fees(cfg)
                max_lev = min(cfg.max_lever, self.settings.paper_max_leverage)
                fill_px, liq = self._fill_price_market(
                    conn, symbol, exec_side, qty_base, cfg.price_end_step
                )
                if fill_px <= 0:
                    raise ValueError("kein gueltiger Preis")
                fee_rate = taker_r if order_type == "market" else maker_r
                notional = order_notional_usdt(qty_base, fill_px)
                fee = calc_transaction_fee_usdt(qty_base, fill_px, fee_rate)
                leverage_decision = allocate_paper_execution_leverage(
                    conn,
                    settings=self.settings,
                    account_row=acc,
                    contract_max_leverage=max_lev,
                    requested_leverage=leverage,
                    signal_payload=signal_payload,
                    symbol=symbol,
                    side=s,
                    qty_base=qty_base,
                    entry_price=fill_px,
                    entry_fee_usdt=fee,
                    timeframe=timeframe,
                    instrument_metadata=cfg.raw.get("instrument_catalog_entry")
                    if isinstance(cfg.raw.get("instrument_catalog_entry"), dict)
                    else None,
                    now_ms=now_ms,
                )
                candidate_leverage = _dec(
                    leverage_decision.get("recommended_leverage")
                    or leverage_decision.get("allowed_leverage")
                    or leverage_decision.get("requested_leverage")
                    or leverage
                )
                if candidate_leverage <= 0:
                    candidate_leverage = Decimal("1")
                projected_margin = notional / candidate_leverage
                account_metrics = build_paper_account_risk_metrics(
                    conn,
                    account_id=account_id,
                    account_row=acc,
                    now_ms=now_ms,
                    projected_margin=projected_margin,
                    projected_fee=fee,
                )
                leverage_audit = leverage_decision.get("audit") or {}
                stop_price = _dec(leverage_audit.get("stop_price"))
                if stop_price <= 0:
                    raise ValueError("shared risk blocked: position_risk_unavailable")
                position_risk_pct = compute_position_risk_pct(
                    entry_price=fill_px,
                    stop_price=stop_price if stop_price > 0 else None,
                    qty_base=qty_base,
                    account_equity=account_metrics["projected_total_equity"],
                    fee_buffer_usdt=fee,
                )
                risk_decision = evaluate_trade_risk(
                    signal=signal_payload or {},
                    limits=build_trade_risk_limits(self.settings),
                    open_positions_count=account_metrics["open_positions_count"] + 1,
                    position_notional_usdt=notional,
                    position_risk_pct=position_risk_pct,
                    projected_margin_usage_pct=account_metrics["projected_margin_usage_pct"],
                    account_drawdown_pct=account_metrics["account_drawdown_pct"],
                    daily_drawdown_pct=account_metrics["daily_drawdown_pct"],
                    weekly_drawdown_pct=account_metrics["weekly_drawdown_pct"],
                    daily_loss_usdt=account_metrics["daily_loss_usdt"],
                    signal_allowed_leverage=leverage_decision.get("allowed_leverage"),
                    signal_recommended_leverage=leverage_decision.get("recommended_leverage"),
                    leverage_cap_reasons_json=leverage_decision.get("cap_reasons_json") or [],
                )
                final_leverage = leverage_decision["recommended_leverage"]
                if risk_decision["trade_action"] == "do_not_trade" or final_leverage is None:
                    reasons = ",".join(risk_decision.get("reasons_json") or [])
                    raise ValueError(
                        f"shared risk blocked{': ' + reasons if reasons else ''}"
                    )
                leverage = Decimal(str(final_leverage))
                margin = notional / leverage
                if equity < margin + fee:
                    raise ValueError("insufficient equity")
                exit_fr: dict[str, Any] | None = None
                if isinstance(signal_payload, dict):
                    rj = signal_payload.get("reasons_json")
                    dcf = None
                    if isinstance(rj, dict):
                        dcf = rj.get("decision_control_flow")
                    if not isinstance(dcf, dict):
                        dcf = signal_payload.get("decision_control_flow")
                    if isinstance(dcf, dict):
                        efr = dcf.get("exit_family_resolution")
                        if isinstance(efr, dict):
                            exit_fr = efr
                ice_dict = (
                    cfg.raw.get("instrument_catalog_entry")
                    if isinstance(cfg.raw.get("instrument_catalog_entry"), dict)
                    else None
                )
                ex_ctx = execution_context_for_position(
                    hints,
                    catalog_entry_dict=ice_dict,
                )
                position_meta = {
                    "leverage_allocator": leverage_decision,
                    "risk_engine": risk_decision,
                    "instrument_catalog_entry": cfg.raw.get("instrument_catalog_entry"),
                    "execution_context": ex_ctx,
                    "requested_leverage": str(leverage_decision["requested_leverage"]),
                    "signal_id": (
                        str(signal_payload.get("signal_id"))
                        if isinstance(signal_payload, dict)
                        and signal_payload.get("signal_id") is not None
                        else None
                    ),
                    **({"exit_family_resolution": exit_fr} if exit_fr else {}),
                }
                sig_uid: UUID | None = None
                if isinstance(signal_payload, dict) and signal_payload.get("signal_id"):
                    try:
                        sig_uid = UUID(str(signal_payload["signal_id"]))
                    except ValueError:
                        sig_uid = None
                pid = repo_positions.insert_position(
                    conn,
                    account_id=account_id,
                    symbol=symbol,
                    side=s,
                    qty_base=qty_base,
                    entry_price_avg=fill_px,
                    leverage=leverage,
                    margin_mode=margin_mode,
                    isolated_margin=margin,
                    state="open",
                    opened_ts_ms=now_ms,
                    updated_ts_ms=now_ms,
                    meta=position_meta,
                    signal_id=sig_uid,
                    canonical_instrument_id=ex_ctx.get("canonical_instrument_id"),
                    market_family=ex_ctx.get("market_family"),
                    product_type=ex_ctx.get("product_type"),
                )
                oid = repo_orders.insert_order(
                    conn,
                    position_id=pid,
                    otype=order_type,
                    side=exec_side,
                    qty_base=qty_base,
                    limit_price=None,
                    state="filled",
                    created_ts_ms=now_ms,
                    filled_ts_ms=now_ms,
                )
                repo_ledgers.insert_fill(
                    conn,
                    order_id=oid,
                    position_id=pid,
                    ts_ms=now_ms,
                    price=fill_px,
                    qty_base=qty_base,
                    liquidity=liq,
                    fee_usdt=fee,
                    notional_usdt=notional,
                )
                repo_ledgers.insert_fee_ledger(
                    conn, position_id=pid, ts_ms=now_ms, fee_usdt=fee, reason="entry"
                )
                new_eq = equity - margin - fee
                repo_accounts.update_account_equity(conn, account_id, new_eq)
                total_equity_after = new_eq + account_metrics["used_margin"] + margin
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type="POSITION_OPENED",
                    details={
                        "account_equity_after": str(new_eq),
                        "account_total_equity_after": str(total_equity_after),
                        "used_margin_after": str(account_metrics["used_margin"] + margin),
                        "position_notional_usdt": str(notional),
                        "projected_margin_usage_pct": risk_decision["metrics"]["projected_margin_usage_pct"],
                        "position_risk_pct": risk_decision["metrics"]["position_risk_pct"],
                    },
                )
                tid_open = (self.settings.billing_prepaid_tenant_id or "default").strip()
                try:
                    enqueue_customer_notify(
                        conn,
                        tenant_id=tid_open,
                        text=(
                            f"Demo-Position eroeffnet: {symbol} {s.upper()} "
                            f"Menge={qty_base} Entry≈{fill_px} USDT"
                        )[:3500],
                        category="paper_order_open",
                        severity="info",
                        dedupe_key=f"paper_order_open:{pid}",
                        audit_actor="paper_broker",
                    )
                except Exception:
                    logger.debug("paper open customer notify skipped", exc_info=True)
        logger.info(
            "opened position position_id=%s fee_usdt=%s notional_usdt=%s",
            pid,
            fee,
            notional,
        )
        publish_trade_opened(
            self.bus,
            position_id=str(pid),
            account_id=str(account_id),
            symbol=symbol,
            side=s,
            qty_base=str(qty_base),
            entry_price_avg=str(fill_px),
            leverage=str(leverage),
            trace={
                "source": "paper-broker",
                "leverage_allocator": leverage_decision,
                "risk_engine": risk_decision,
            },
        )
        return {
            "position_id": str(pid),
            "fill_price": str(fill_px),
            "fee_usdt": str(fee),
            "notional_usdt": str(notional),
            "isolated_margin": str(margin),
            "account_equity_after": str(new_eq),
            "recommended_leverage": final_leverage,
            "leverage_allocator": leverage_decision,
            "risk_engine": risk_decision,
        }

    def close_position(
        self,
        position_id: UUID,
        qty_base: Decimal,
        order_type: str,
        ts_ms: int | None = None,
    ) -> dict[str, Any]:
        now_ms = ts_ms if ts_ms is not None else int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                out = self._close_qty_in_conn(conn, position_id, qty_base, order_type, now_ms)
        symbol = str(out["symbol"])
        new_qty = out["new_qty"]
        st = str(out["state"])
        publish_trade_updated(
            self.bus, position_id=str(position_id), symbol=symbol, qty_base=str(new_qty), state=st
        )
        if new_qty == 0:
            publish_trade_closed_evt(
                self.bus, position_id=str(position_id), symbol=symbol, reason="CLOSED"
            )
        return {
            "position_id": str(position_id),
            "closed_qty": str(qty_base),
            "remaining_qty": str(new_qty),
            "fill_price": str(out["fill_price"]),
            "fee_usdt": str(out["fee_usdt"]),
            "realized_pnl": str(out["realized_pnl"]),
            "state": st,
            "account_equity_after": str(out["account_equity_after"]),
        }

    def process_tick(self, now_ms: int) -> dict[str, Any]:
        liquidated: list[str] = []
        funded: list[str] = []
        stop_tp_closed: list[str] = []
        with paper_connect(self.settings.database_url, autocommit=True) as conn:
            positions = repo_positions.list_open_positions(conn)
            for pos in positions:
                if self.settings.paper_stop_tp_enabled:
                    done = run_stop_tp_for_position(self, conn, pos, now_ms)
                    if done:
                        stop_tp_closed.append(str(pos["position_id"]))
            positions = repo_positions.list_open_positions(conn)
            for pos in positions:
                pid = UUID(str(pos["position_id"]))
                sym = str(pos["symbol"])
                mark, _, _ = self.get_mark_and_bid_ask(conn, sym)
                if mark <= 0:
                    continue
                fees = repo_ledgers.sum_fees_for_position(conn, pid)
                fund_net = repo_ledgers.sum_funding_for_position(conn, pid)
                if should_liquidate_approx(
                    isolated_margin=_dec(pos["isolated_margin"]),
                    qty=_dec(pos["qty_base"]),
                    entry_avg=_dec(pos["entry_price_avg"]),
                    mark=mark,
                    side=str(pos["side"]),
                    accrued_fees=fees,
                    net_funding_ledger=fund_net,
                    maintenance_margin_rate=Decimal(self.settings.paper_mmr_base),
                    liq_fee_buffer_usdt=Decimal(self.settings.paper_liq_fee_buffer_usdt),
                ):
                    self._liquidate_position(conn, pos, mark, now_ms)
                    liquidated.append(str(pid))
            self._maybe_book_funding(conn, now_ms, funded)
            if self.strategy_engine is not None:
                self.strategy_engine.run_after_market_tick(conn, now_ms)
        return {
            "now_ms": now_ms,
            "liquidated": liquidated,
            "funding_booked": funded,
            "stop_tp_closed": stop_tp_closed,
        }

    def plan_auto(
        self,
        position_id: UUID,
        *,
        timeframe: str,
        preferred_trigger_type: str | None = None,
        method_mix: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                pos = repo_positions.get_position(conn, position_id)
                if pos is None:
                    raise ValueError("position not found")
                if str(pos["state"]) in ("closed", "liquidated"):
                    raise ValueError("position not open")
                stop_plan, tp_plan, score, rr_s = build_auto_plan_bundle(
                    conn,
                    position_row=pos,
                    settings=self.settings,
                    timeframe=timeframe.strip(),
                    preferred_stop_trigger=preferred_trigger_type,
                    method_mix=method_mix,
                )
                meta = _meta_dict(pos.get("meta"))
                leverage_allocator = meta.get("leverage_allocator") if isinstance(meta.get("leverage_allocator"), dict) else {}
                risk_engine = meta.get("risk_engine") if isinstance(meta.get("risk_engine"), dict) else {}
                ice = meta.get("instrument_catalog_entry")
                if not isinstance(ice, dict):
                    ice = {}
                mf_plan = str(
                    ice.get("market_family")
                    or (meta.get("execution_context") or {}).get("market_family")
                    or self.settings.bitget_market_family
                )
                exit_validation = validate_exit_plan(
                    side=str(pos["side"]),
                    entry_price=_dec(pos["entry_price_avg"]),
                    stop_plan=stop_plan,
                    tp_plan=tp_plan,
                    leverage=_dec(pos.get("leverage")),
                    allowed_leverage=(
                        int(leverage_allocator.get("allowed_leverage"))
                        if leverage_allocator.get("allowed_leverage") not in (None, "")
                        else None
                    ),
                    max_position_risk_pct=self.settings.risk_max_position_risk_pct,
                    risk_trade_action=str(risk_engine.get("trade_action") or ""),
                    market_family=mf_plan,
                    price_tick_size=_dec(ice.get("price_tick_size")),
                    quantity_step=_dec(ice.get("quantity_step")),
                    quantity_min=_dec(ice.get("quantity_min")),
                    quantity_max=_dec(ice.get("quantity_max")),
                    trading_status=str(ice.get("trading_status") or ""),
                )
                if not exit_validation["valid"]:
                    raise ValueError(
                        "exit plan contradicts shared risk/leverage: "
                        + ",".join(exit_validation["reasons"])
                    )
                ver = f"auto-{now_ms}"
                repo_positions.update_position_plan(
                    conn,
                    position_id,
                    plan_version=ver,
                    stop_plan_json=stop_plan,
                    tp_plan_json=tp_plan,
                    stop_quality_score=score,
                    rr_estimate=rr_s,
                    plan_updated_ts_ms=now_ms,
                )
                warns = (stop_plan.get("quality") or {}).get("risk_warnings") or []
                repo_position_events.insert_position_event(
                    conn,
                    position_id=position_id,
                    ts_ms=now_ms,
                    event_type="PLAN_CREATED",
                    details={"plan_version": ver, "timeframe": timeframe},
                )
            logger.info(
                "plan_auto_created position_id=%s stop_quality_score=%s plan_version=%s",
                position_id,
                score,
                ver,
            )
            if warns:
                publish_risk_alert(
                    self.bus,
                    symbol=str(pos["symbol"]),
                    position_id=str(position_id),
                    warnings=[str(w) for w in warns],
                    stop_quality_score=score,
                )
                tid = (self.settings.billing_prepaid_tenant_id or "default").strip()
                try:
                    enqueue_customer_notify(
                        conn,
                        tenant_id=tid,
                        text=(
                            f"Risiko-Hinweis ({str(pos['symbol'])}): "
                            + "; ".join([str(w) for w in warns])
                        )[:3500],
                        category="risk_warning",
                        severity="warning",
                        dedupe_key=f"risk_plan:{position_id}:{score}",
                        audit_actor="paper_broker",
                    )
                except psycopg.errors.UndefinedTable:
                    pass
            return {
                "position_id": str(position_id),
                "plan_version": ver,
                "stop_plan": stop_plan,
                "tp_plan": tp_plan,
                "stop_quality_score": score,
                "rr_estimate": rr_s,
            }

    def get_position_plan(self, position_id: UUID) -> dict[str, Any]:
        with paper_connect(self.settings.database_url, autocommit=True) as conn:
            pos = repo_positions.get_position(conn, position_id)
            if pos is None:
                raise ValueError("position not found")
        return {
            "position_id": str(position_id),
            "state": str(pos["state"]),
            "plan_version": pos.get("plan_version"),
            "stop_plan": parse_plan_json(pos.get("stop_plan_json")),
            "tp_plan": parse_plan_json(pos.get("tp_plan_json")),
            "stop_quality_score": pos.get("stop_quality_score"),
            "rr_estimate": str(pos["rr_estimate"]) if pos.get("rr_estimate") is not None else None,
            "plan_updated_ts_ms": pos.get("plan_updated_ts_ms"),
        }

    def plan_override(
        self,
        position_id: UUID,
        *,
        stop_patch: dict[str, Any] | None,
        tp_patch: dict[str, Any] | None,
    ) -> dict[str, Any]:
        now_ms = int(time.time() * 1000)
        with paper_connect(self.settings.database_url) as conn:
            with conn.transaction():
                pos = repo_positions.get_position(conn, position_id)
                if pos is None:
                    raise ValueError("position not found")
                if str(pos["state"]) in ("closed", "liquidated"):
                    raise ValueError("position not open")
                cur_stop = parse_plan_json(pos.get("stop_plan_json")) or {}
                cur_tp = parse_plan_json(pos.get("tp_plan_json")) or {}
                new_stop, new_tp = merge_plan_override(
                    cur_stop, cur_tp, stop_patch, tp_patch
                )
                meta = _meta_dict(pos.get("meta"))
                leverage_allocator = meta.get("leverage_allocator") if isinstance(meta.get("leverage_allocator"), dict) else {}
                risk_engine = meta.get("risk_engine") if isinstance(meta.get("risk_engine"), dict) else {}
                exit_validation = validate_exit_plan(
                    side=str(pos["side"]),
                    entry_price=_dec(pos["entry_price_avg"]),
                    stop_plan=new_stop,
                    tp_plan=new_tp,
                    leverage=_dec(pos.get("leverage")),
                    allowed_leverage=(
                        int(leverage_allocator.get("allowed_leverage"))
                        if leverage_allocator.get("allowed_leverage") not in (None, "")
                        else None
                    ),
                    max_position_risk_pct=self.settings.risk_max_position_risk_pct,
                    risk_trade_action=str(risk_engine.get("trade_action") or ""),
                    market_family=self.settings.bitget_market_family,
                    price_tick_size=_dec((meta.get("instrument_catalog_entry") or {}).get("price_tick_size")),
                    quantity_step=_dec((meta.get("instrument_catalog_entry") or {}).get("quantity_step")),
                    quantity_min=_dec((meta.get("instrument_catalog_entry") or {}).get("quantity_min")),
                    quantity_max=_dec((meta.get("instrument_catalog_entry") or {}).get("quantity_max")),
                    trading_status=str((meta.get("instrument_catalog_entry") or {}).get("trading_status") or ""),
                )
                if not exit_validation["valid"]:
                    raise ValueError(
                        "exit plan contradicts shared risk/leverage: "
                        + ",".join(exit_validation["reasons"])
                    )
                ver = str(pos.get("plan_version") or "v0") + "+ov"
                repo_positions.update_position_plan(
                    conn,
                    position_id,
                    plan_version=ver,
                    stop_plan_json=new_stop,
                    tp_plan_json=new_tp,
                    stop_quality_score=int(pos.get("stop_quality_score") or 0),
                    rr_estimate=str(pos["rr_estimate"]) if pos.get("rr_estimate") is not None else None,
                    plan_updated_ts_ms=now_ms,
                )
                repo_position_events.insert_position_event(
                    conn,
                    position_id=position_id,
                    ts_ms=now_ms,
                    event_type="PLAN_UPDATED",
                    details={"plan_version": ver},
                )
            return {
                "position_id": str(position_id),
                "plan_version": ver,
                "stop_plan": new_stop,
                "tp_plan": new_tp,
            }

    def _liquidate_position(
        self,
        conn: psycopg.Connection[Any],
        pos: dict[str, Any],
        mark: Decimal,
        now_ms: int,
    ) -> None:
        pid = UUID(str(pos["position_id"]))
        symbol = str(pos["symbol"])
        side = str(pos["side"])
        qty0 = _dec(pos["qty_base"])
        entry = _dec(pos["entry_price_avg"])
        iso = _dec(pos["isolated_margin"])
        account_id = UUID(str(pos["account_id"]))
        acc = repo_accounts.get_account(conn, account_id)
        equity = _dec(acc["equity"]) if acc else Decimal("0")
        liq_meta = json.loads(pos["meta"]) if isinstance(pos["meta"], str) else (pos["meta"] or {})
        cfg = self.contract_provider.get(
            symbol,
            conn,
            signal_payload=_contract_payload_from_position_meta(liq_meta),
        )
        _, taker_r = self.contract_provider.effective_fees(cfg)
        fee = calc_transaction_fee_usdt(qty0, mark, taker_r)
        notional = order_notional_usdt(qty0, mark)
        if side == "long":
            realized = (mark - entry) * qty0
        else:
            realized = (entry - mark) * qty0
        margin_release = iso
        oid = repo_orders.insert_order(
            conn,
            position_id=pid,
            otype="market",
            side="sell" if side == "long" else "buy",
            qty_base=qty0,
            limit_price=None,
            state="filled",
            created_ts_ms=now_ms,
            filled_ts_ms=now_ms,
        )
        repo_ledgers.insert_fill(
            conn,
            order_id=oid,
            position_id=pid,
            ts_ms=now_ms,
            price=mark,
            qty_base=qty0,
            liquidity="taker",
            fee_usdt=fee,
            notional_usdt=notional,
        )
        repo_ledgers.insert_fee_ledger(
            conn, position_id=pid, ts_ms=now_ms, fee_usdt=fee, reason="exit"
        )
        new_eq = equity + margin_release + realized - fee
        repo_accounts.update_account_equity(conn, account_id, new_eq)
        meta = _meta_dict(pos.get("meta"))
        meta["liquidation"] = True
        repo_positions.set_position_liquidated(
            conn, pid, updated_ts_ms=now_ms, closed_ts_ms=now_ms, meta=meta
        )
        post_metrics = build_paper_account_risk_metrics(
            conn,
            account_id=account_id,
            account_row={"equity": str(new_eq), "initial_equity": acc.get("initial_equity") if acc else None},
            now_ms=now_ms,
        )
        repo_position_events.insert_position_event(
            conn,
            position_id=pid,
            ts_ms=now_ms,
            event_type="POSITION_LIQUIDATED",
            details={
                "account_equity_after": str(new_eq),
                "account_total_equity_after": str(post_metrics["total_equity"]),
                "used_margin_after": str(post_metrics["used_margin"]),
                "realized_pnl": str(realized),
                "fee_usdt": str(fee),
            },
        )
        logger.info("liquidated position_id=%s (approx)", pid)
        publish_trade_updated(
            self.bus, position_id=str(pid), symbol=symbol, qty_base="0", state="liquidated"
        )
        publish_trade_closed_evt(
            self.bus,
            position_id=str(pid),
            symbol=symbol,
            reason="LIQUIDATED_APPROX",
        )

    def _maybe_book_funding(
        self, conn: psycopg.Connection[Any], now_ms: int, funded: list[str]
    ) -> None:
        sf = self.sim_funding
        if sf is None or sf.next_update_ms <= 0:
            return
        if now_ms < sf.next_update_ms:
            return
        rate = sf.funding_rate
        src = "sim" if self.settings.paper_sim_mode else "events"
        positions = repo_positions.list_open_positions(conn)
        for pos in positions:
            pid = UUID(str(pos["position_id"]))
            sym = str(pos["symbol"])
            mark, _, _ = self.get_mark_and_bid_ask(conn, sym)
            if mark <= 0:
                continue
            qty = _dec(pos["qty_base"])
            val = abs(qty * mark)
            amt = calc_funding_usdt(val, rate, str(pos["side"]))
            repo_ledgers.insert_funding_ledger(
                conn,
                position_id=pid,
                ts_ms=now_ms,
                funding_rate=rate,
                position_value_usdt=val,
                funding_usdt=amt,
                source=src,
            )
            acc_id = UUID(str(pos["account_id"]))
            acc = repo_accounts.get_account(conn, acc_id)
            if acc:
                new_eq = _dec(acc["equity"]) + amt
                repo_accounts.update_account_equity(conn, acc_id, new_eq)
                post_metrics = build_paper_account_risk_metrics(
                    conn,
                    account_id=acc_id,
                    account_row={**acc, "equity": str(new_eq)},
                    now_ms=now_ms,
                )
                repo_position_events.insert_position_event(
                    conn,
                    position_id=pid,
                    ts_ms=now_ms,
                    event_type="FUNDING_BOOKED",
                    details={
                        "account_equity_after": str(new_eq),
                        "account_total_equity_after": str(post_metrics["total_equity"]),
                        "used_margin_after": str(post_metrics["used_margin"]),
                        "funding_usdt": str(amt),
                    },
                )
            funded.append(str(pid))
            publish_funding_booked(
                self.bus,
                position_id=str(pid),
                symbol=sym,
                funding_rate=str(rate),
                amount=str(amt),
                ts_ms=now_ms,
            )
        interval_ms = sf.funding_interval_hours * 3600_000
        sf.next_update_ms = sf.next_update_ms + interval_ms
