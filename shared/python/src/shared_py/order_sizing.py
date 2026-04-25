from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Literal

ExecutionMode = Literal["paper", "shadow", "live"]


@dataclass(frozen=True)
class OrderSizingInput:
    symbol: str
    market_family: str
    risk_tier: str | None
    liquidity_tier: str | None
    account_equity: float | None
    equity_fresh: bool
    available_margin: float | None
    max_account_margin_usage: float
    max_position_risk_pct: float
    max_daily_loss: float
    max_weekly_loss: float
    current_daily_loss: float
    current_weekly_loss: float
    current_drawdown: float
    max_drawdown_limit: float
    stop_distance_pct: float | None
    expected_slippage_pct: float
    fee_pct: float
    leverage_cap: int
    min_qty: float
    min_notional: float
    qty_step: float
    open_positions_notional: float
    pending_orders_notional: float
    mode: ExecutionMode


@dataclass(frozen=True)
class OrderSizingResult:
    suggested_qty: float
    max_allowed_qty: float
    max_notional: float
    risk_per_trade_pct: float
    leverage_cap: int
    margin_usage_pct: float
    block_reasons: list[str]
    reduced_reasons: list[str]


def _tier_blocks_size(risk_tier: str | None) -> bool:
    normalized = (risk_tier or "").upper()
    return normalized in {"", "RISK_TIER_4_SHADOW_ONLY", "RISK_TIER_5_BANNED_OR_DELISTED", "RISK_TIER_0_BLOCKED"}


def _to_step_down(value: float, step: float) -> float:
    if step <= 0:
        return 0.0
    v = Decimal(str(value))
    s = Decimal(str(step))
    rounded = (v / s).to_integral_value(rounding=ROUND_DOWN) * s
    return float(rounded)


def validate_order_sizing_context(data: OrderSizingInput) -> list[str]:
    reasons: list[str] = []
    if data.account_equity is None or data.account_equity <= 0:
        reasons.append("equity_fehlt")
    if not data.equity_fresh:
        reasons.append("equity_stale")
    if not data.risk_tier:
        reasons.append("risk_tier_fehlt")
    if not data.liquidity_tier:
        reasons.append("liquiditaetsstatus_fehlt")
    if data.available_margin is None or data.available_margin <= 0:
        reasons.append("available_margin_fehlt")
    if data.stop_distance_pct is None or data.stop_distance_pct <= 0:
        reasons.append("stop_distance_fehlt")
    if data.qty_step <= 0:
        reasons.append("precision_step_ungueltig")
    return reasons


def compute_max_notional_for_asset(data: OrderSizingInput) -> float:
    if data.account_equity is None or data.available_margin is None:
        return 0.0
    budget_by_margin = max(0.0, data.available_margin * data.max_account_margin_usage)
    budget_by_equity = max(0.0, data.account_equity * data.max_position_risk_pct * max(1, data.leverage_cap))
    remaining = max(0.0, budget_by_margin - data.open_positions_notional - data.pending_orders_notional)
    return min(budget_by_equity, remaining)


def apply_asset_tier_sizing_caps(*, risk_tier: str | None, max_notional: float) -> tuple[float, list[str]]:
    reduced: list[str] = []
    normalized = (risk_tier or "").upper()
    tier_cap = {
        "RISK_TIER_1_MAJOR_LIQUID": 20_000.0,
        "RISK_TIER_2_LIQUID": 10_000.0,
        "RISK_TIER_3_ELEVATED_RISK": 4_000.0,
        "RISK_TIER_4_SHADOW_ONLY": 0.0,
        "RISK_TIER_5_BANNED_OR_DELISTED": 0.0,
        "RISK_TIER_0_BLOCKED": 0.0,
    }.get(normalized, 0.0)
    out = min(max_notional, tier_cap)
    if out < max_notional:
        reduced.append("asset_tier_cap_reduziert")
    return out, reduced


def apply_liquidity_sizing_cap(*, liquidity_tier: str | None, max_notional: float) -> tuple[float, list[str]]:
    reduced: list[str] = []
    normalized = (liquidity_tier or "").upper()
    liquidity_cap = {
        "TIER_1": max_notional,
        "TIER_2": min(max_notional, 8_000.0),
        "TIER_3": min(max_notional, 1_500.0),
        "TIER_4": 0.0,
        "TIER_5": 0.0,
    }.get(normalized, 0.0)
    if liquidity_cap < max_notional:
        reduced.append("liquiditaets_cap_reduziert")
    return liquidity_cap, reduced


def compute_order_qty_from_risk(data: OrderSizingInput) -> OrderSizingResult:
    block_reasons = validate_order_sizing_context(data)
    reduced_reasons: list[str] = []
    if data.current_daily_loss >= data.max_daily_loss:
        block_reasons.append("daily_loss_limit_ueberschritten")
    if data.current_weekly_loss >= data.max_weekly_loss:
        block_reasons.append("weekly_loss_limit_ueberschritten")
    if data.current_drawdown >= data.max_drawdown_limit:
        block_reasons.append("drawdown_limit_ueberschritten")
    if _tier_blocks_size(data.risk_tier):
        block_reasons.append("risk_tier_blockiert_groesse")

    max_notional = compute_max_notional_for_asset(data)
    max_notional, tier_reduced = apply_asset_tier_sizing_caps(risk_tier=data.risk_tier, max_notional=max_notional)
    reduced_reasons.extend(tier_reduced)
    max_notional, liq_reduced = apply_liquidity_sizing_cap(liquidity_tier=data.liquidity_tier, max_notional=max_notional)
    reduced_reasons.extend(liq_reduced)

    if data.mode == "live":
        max_notional *= 0.7
        reduced_reasons.append("live_modus_konservativer_cap")

    denom = (data.stop_distance_pct or 0.0) + data.expected_slippage_pct + data.fee_pct
    if denom <= 0:
        block_reasons.append("risk_denominator_ungueltig")
        denom = 1.0
    risk_budget = (data.account_equity or 0.0) * data.max_position_risk_pct
    suggested_notional = min(max_notional, risk_budget / denom if denom > 0 else 0.0)
    if suggested_notional <= 0:
        block_reasons.append("keine_sichere_groesse_verfuegbar")
    qty = _to_step_down(suggested_notional, data.qty_step)
    if qty > suggested_notional:
        block_reasons.append("precision_rounding_erhoeht_risiko")
    if qty < data.min_qty:
        block_reasons.append("min_qty_unterschritten")
    if suggested_notional < data.min_notional:
        block_reasons.append("min_notional_unterschritten")

    margin_usage_pct = 0.0
    if data.available_margin and data.available_margin > 0:
        margin_usage_pct = ((data.open_positions_notional + data.pending_orders_notional + qty) / data.available_margin)
    if margin_usage_pct > data.max_account_margin_usage:
        block_reasons.append("margin_usage_ueber_limit")

    return OrderSizingResult(
        suggested_qty=0.0 if block_reasons else qty,
        max_allowed_qty=max(0.0, _to_step_down(max_notional, data.qty_step)),
        max_notional=max_notional,
        risk_per_trade_pct=data.max_position_risk_pct,
        leverage_cap=data.leverage_cap,
        margin_usage_pct=margin_usage_pct,
        block_reasons=list(dict.fromkeys(block_reasons)),
        reduced_reasons=list(dict.fromkeys(reduced_reasons)),
    )


def order_sizing_blocks_live(result: OrderSizingResult) -> bool:
    return len(result.block_reasons) > 0 or result.suggested_qty <= 0


def build_order_sizing_explanation_de(result: OrderSizingResult) -> str:
    if result.block_reasons:
        reasons = ", ".join(result.block_reasons)
        return f"Order-Sizing blockiert: {reasons}. Vorschlag bleibt 0."
    reduced = ", ".join(result.reduced_reasons) if result.reduced_reasons else "keine"
    return (
        f"Vorgeschlagene Groesse {result.suggested_qty:.6f}, max erlaubt {result.max_allowed_qty:.6f}, "
        f"Leverage-Cap {result.leverage_cap}x, Margin-Nutzung {result.margin_usage_pct:.4f}. "
        f"Reduktionen: {reduced}."
    )
