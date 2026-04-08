from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from shared_py.signal_contracts import DecisionState, TradeAction

RISK_ENGINE_POLICY_VERSION = "shared-risk-v1"

_COST_REASON_CODES = {
    "spread_too_wide",
    "execution_cost_too_high",
    "adverse_funding_too_high",
}
_UNCERTAINTY_REASON_CODES = {
    "model_ood_alert",
    "uncertainty_above_threshold",
    "missing_take_trade_prediction",
    "missing_target_projection_output",
}


@dataclass(frozen=True)
class TradeRiskLimits:
    min_signal_strength: int
    min_probability: float
    min_risk_score: int
    min_expected_return_bps: float
    max_expected_mae_bps: float
    min_projected_rr: float
    min_allowed_leverage: int
    max_position_risk_pct: float
    max_account_margin_usage: float
    max_account_drawdown_pct: float
    max_daily_drawdown_pct: float
    max_weekly_drawdown_pct: float
    max_daily_loss_usdt: float
    max_position_notional_usdt: float
    max_concurrent_positions: int


def build_trade_risk_limits(settings: Any) -> TradeRiskLimits:
    return TradeRiskLimits(
        min_signal_strength=int(getattr(settings, "risk_min_signal_strength")),
        min_probability=float(getattr(settings, "risk_min_probability")),
        min_risk_score=int(getattr(settings, "risk_min_risk_score")),
        min_expected_return_bps=float(getattr(settings, "risk_min_expected_return_bps")),
        max_expected_mae_bps=float(getattr(settings, "risk_max_expected_mae_bps")),
        min_projected_rr=float(getattr(settings, "risk_min_projected_rr")),
        min_allowed_leverage=int(getattr(settings, "risk_allowed_leverage_min")),
        max_position_risk_pct=float(getattr(settings, "risk_max_position_risk_pct")),
        max_account_margin_usage=float(getattr(settings, "risk_max_account_margin_usage")),
        max_account_drawdown_pct=float(getattr(settings, "risk_max_account_drawdown_pct")),
        max_daily_drawdown_pct=float(getattr(settings, "risk_max_daily_drawdown_pct")),
        max_weekly_drawdown_pct=float(getattr(settings, "risk_max_weekly_drawdown_pct")),
        max_daily_loss_usdt=float(getattr(settings, "risk_max_daily_loss_usdt")),
        max_position_notional_usdt=float(getattr(settings, "risk_max_position_notional_usdt")),
        max_concurrent_positions=int(getattr(settings, "risk_max_concurrent_positions")),
    )


def compute_total_equity(*, available_equity: Any, used_margin: Any) -> Decimal:
    available = _coerce_decimal(available_equity) or Decimal("0")
    margin = _coerce_decimal(used_margin) or Decimal("0")
    total = available + margin
    return total if total > 0 else Decimal("0")


def compute_margin_usage_pct(*, total_equity: Any, used_margin: Any) -> float | None:
    equity = _coerce_decimal(total_equity)
    margin = _coerce_decimal(used_margin)
    if equity is None or margin is None or equity <= 0:
        return None
    usage = margin / equity
    return round(float(max(Decimal("0"), usage)), 6)


def compute_position_risk_pct(
    *,
    entry_price: Any,
    stop_price: Any,
    qty_base: Any,
    account_equity: Any,
    fee_buffer_usdt: Any = None,
) -> float | None:
    entry = _coerce_decimal(entry_price)
    stop = _coerce_decimal(stop_price)
    qty = _coerce_decimal(qty_base)
    equity = _coerce_decimal(account_equity)
    fee_buffer = _coerce_decimal(fee_buffer_usdt) or Decimal("0")
    if entry is None or stop is None or qty is None or equity is None or equity <= 0:
        return None
    price_risk = abs(entry - stop) * abs(qty)
    total_risk = price_risk + max(Decimal("0"), fee_buffer)
    return round(float(total_risk / equity), 6)


def compute_drawdown_from_points(
    *,
    current_equity: Any,
    equity_points: Sequence[Any] | None = None,
) -> dict[str, Any]:
    current = _coerce_decimal(current_equity)
    if current is None or current <= 0:
        return {"peak_equity": None, "drawdown_pct": None, "loss_usdt": None}
    peak = current
    for point in equity_points or ():
        value = _coerce_decimal(point)
        if value is None or value <= 0:
            continue
        peak = max(peak, value)
    loss = max(Decimal("0"), peak - current)
    drawdown_pct = Decimal("0")
    if peak > 0:
        drawdown_pct = loss / peak
    return {
        "peak_equity": format(peak, "f"),
        "drawdown_pct": round(float(drawdown_pct), 6),
        "loss_usdt": format(loss, "f"),
    }


def evaluate_trade_risk(
    *,
    signal: Mapping[str, Any],
    limits: TradeRiskLimits,
    open_positions_count: int | None = None,
    position_notional_usdt: Any = None,
    position_risk_pct: float | None = None,
    projected_margin_usage_pct: float | None = None,
    account_drawdown_pct: float | None = None,
    daily_drawdown_pct: float | None = None,
    weekly_drawdown_pct: float | None = None,
    daily_loss_usdt: Any = None,
    signal_allowed_leverage: Any = None,
    signal_recommended_leverage: Any = None,
    leverage_cap_reasons_json: Sequence[Any] | None = None,
    operational_staleness_reasons: Sequence[Any] | None = None,
    shock_reasons: Sequence[Any] | None = None,
) -> dict[str, Any]:
    signal_reasons: list[str] = []
    market_reasons: list[str] = []
    account_reasons: list[str] = []
    position_reasons: list[str] = []

    trade_action = str(signal.get("trade_action") or "").strip().lower()
    if trade_action == "do_not_trade":
        signal_reasons.append("trade_action_do_not_trade")

    decision_state = str(signal.get("final_decision_state") or signal.get("decision_state") or "").strip().lower()
    if decision_state and decision_state != "accepted":
        signal_reasons.append("not_accepted")

    if _bool_value(signal.get("rejection_state")):
        signal_reasons.append("rejection_active")

    strength = _coerce_float(signal.get("signal_strength_0_100"))
    if strength is not None and strength < limits.min_signal_strength:
        signal_reasons.append("strength_low")

    probability = _coerce_float(signal.get("take_trade_prob"))
    if probability is None:
        probability = _coerce_float(signal.get("probability_0_1"))
    if probability is not None and probability < limits.min_probability:
        signal_reasons.append("prob_low")

    risk_score = _coerce_float(signal.get("risk_score_0_100"))
    if risk_score is not None and risk_score < limits.min_risk_score:
        signal_reasons.append("risk_low")

    expected_return = _coerce_float(signal.get("expected_return_bps"))
    if expected_return is not None and expected_return < limits.min_expected_return_bps:
        signal_reasons.append("expected_return_low")

    expected_mae = _coerce_float(signal.get("expected_mae_bps"))
    if expected_mae is not None and expected_mae > limits.max_expected_mae_bps:
        signal_reasons.append("expected_mae_high")

    projected_rr = _projected_rr(signal)
    if projected_rr is not None and projected_rr < limits.min_projected_rr:
        signal_reasons.append("projected_rr_low")

    raw_rejection_reasons = _unique_strs(
        signal.get("rejection_reasons_json") or signal.get("rejection_reasons") or []
    )
    raw_abstention_reasons = _unique_strs(signal.get("abstention_reasons_json") or [])
    raw_uncertainty_reasons = _unique_strs(signal.get("uncertainty_reasons_json") or [])
    raw_leverage_reasons = _unique_strs(
        leverage_cap_reasons_json
        if leverage_cap_reasons_json is not None
        else signal.get("leverage_cap_reasons_json") or []
    )

    quality_gate_passed = _quality_gate_passed(signal)
    stale_signal_reasons = [
        reason
        for reason in raw_rejection_reasons + raw_abstention_reasons + raw_uncertainty_reasons
        if _is_stale_reason(reason)
    ]
    if quality_gate_passed is False and not stale_signal_reasons:
        stale_signal_reasons.append("quality_gate_failed")
    market_reasons.extend(stale_signal_reasons)

    market_regime = str(signal.get("market_regime") or "").strip().lower()
    if market_regime == "shock":
        market_reasons.append("market_regime_shock")
    market_reasons.extend(_unique_strs(shock_reasons or []))

    cost_reasons = [
        reason
        for reason in raw_rejection_reasons + raw_abstention_reasons
        if reason in _COST_REASON_CODES
    ]
    market_reasons.extend(cost_reasons)

    uncertainty_reasons = [
        reason
        for reason in raw_abstention_reasons + raw_uncertainty_reasons
        if reason in _UNCERTAINTY_REASON_CODES
    ]
    market_reasons.extend(uncertainty_reasons)
    market_reasons.extend(_unique_strs(operational_staleness_reasons or []))

    allowed_leverage = _coerce_int(
        signal_allowed_leverage
        if signal_allowed_leverage is not None
        else signal.get("allowed_leverage")
    )
    recommended_leverage = _coerce_int(
        signal_recommended_leverage
        if signal_recommended_leverage is not None
        else signal.get("recommended_leverage")
    )
    if (
        allowed_leverage is not None
        and allowed_leverage < limits.min_allowed_leverage
    ) or (
        recommended_leverage is not None
        and recommended_leverage < limits.min_allowed_leverage
    ) or any("allowed_leverage_below_minimum" in reason for reason in raw_leverage_reasons):
        position_reasons.append("allowed_leverage_below_minimum")

    if open_positions_count is not None and open_positions_count >= limits.max_concurrent_positions:
        account_reasons.append("max_concurrent_positions_exceeded")

    notional = _coerce_decimal(position_notional_usdt)
    if notional is not None and notional > Decimal(str(limits.max_position_notional_usdt)):
        position_reasons.append("position_notional_limit_exceeded")

    if (
        position_risk_pct is not None
        and position_risk_pct >= limits.max_position_risk_pct
    ):
        position_reasons.append("position_risk_limit_exceeded")

    if (
        projected_margin_usage_pct is not None
        and projected_margin_usage_pct >= limits.max_account_margin_usage
    ):
        account_reasons.append("account_margin_usage_limit_exceeded")

    if (
        account_drawdown_pct is not None
        and account_drawdown_pct >= limits.max_account_drawdown_pct
    ):
        account_reasons.append("account_drawdown_limit_exceeded")

    if (
        daily_drawdown_pct is not None
        and daily_drawdown_pct >= limits.max_daily_drawdown_pct
    ):
        account_reasons.append("daily_drawdown_limit_exceeded")

    if (
        weekly_drawdown_pct is not None
        and weekly_drawdown_pct >= limits.max_weekly_drawdown_pct
    ):
        account_reasons.append("weekly_drawdown_limit_exceeded")

    daily_loss = _coerce_decimal(daily_loss_usdt)
    if daily_loss is not None and daily_loss >= Decimal(str(limits.max_daily_loss_usdt)):
        account_reasons.append("daily_loss_limit_exceeded")

    reasons = _unique_strs(signal_reasons + market_reasons + account_reasons + position_reasons)
    trade_decision: TradeAction = "allow_trade" if not reasons else "do_not_trade"
    decision: DecisionState = "accepted" if not reasons else "rejected"
    return {
        "policy_version": RISK_ENGINE_POLICY_VERSION,
        "trade_action": trade_decision,
        "decision_state": decision,
        "decision_reason": reasons[0] if reasons else None,
        "reasons_json": reasons,
        "signal_reasons_json": _unique_strs(signal_reasons),
        "market_reasons_json": _unique_strs(market_reasons),
        "account_reasons_json": _unique_strs(account_reasons),
        "position_reasons_json": _unique_strs(position_reasons),
        "limits": asdict(limits),
        "metrics": {
            "open_positions_count": open_positions_count,
            "position_notional_usdt": _decimal_json(notional),
            "position_risk_pct": _round_float(position_risk_pct),
            "projected_margin_usage_pct": _round_float(projected_margin_usage_pct),
            "account_drawdown_pct": _round_float(account_drawdown_pct),
            "daily_drawdown_pct": _round_float(daily_drawdown_pct),
            "weekly_drawdown_pct": _round_float(weekly_drawdown_pct),
            "daily_loss_usdt": _decimal_json(daily_loss),
            "allowed_leverage": allowed_leverage,
            "recommended_leverage": recommended_leverage,
            "projected_rr": _round_float(projected_rr),
        },
        "context": {
            "trade_action": trade_action or None,
            "decision_state": decision_state or None,
            "market_regime": market_regime or None,
            "quality_gate_passed": quality_gate_passed,
            "rejection_reasons_json": raw_rejection_reasons,
            "abstention_reasons_json": raw_abstention_reasons,
            "uncertainty_reasons_json": raw_uncertainty_reasons,
            "leverage_cap_reasons_json": raw_leverage_reasons,
        },
    }


def _quality_gate_passed(signal: Mapping[str, Any]) -> bool | None:
    quality_gate = _as_dict(signal.get("quality_gate"))
    if "passed" in quality_gate:
        return _bool_value(quality_gate.get("passed"))
    source_snapshot = _as_dict(signal.get("source_snapshot_json"))
    nested_quality_gate = _as_dict(source_snapshot.get("quality_gate"))
    if "passed" in nested_quality_gate:
        return _bool_value(nested_quality_gate.get("passed"))
    return None


def _projected_rr(signal: Mapping[str, Any]) -> float | None:
    expected_mae = _coerce_float(signal.get("expected_mae_bps"))
    expected_mfe = _coerce_float(signal.get("expected_mfe_bps"))
    if expected_mae is None or expected_mfe is None or expected_mae <= 0:
        return None
    return expected_mfe / expected_mae


def _is_stale_reason(reason: str) -> bool:
    lowered = str(reason).strip().lower()
    return lowered.startswith("stale_") or lowered.startswith("missing_") or lowered == "liquidity_context_fallback"


def _unique_strs(values: Sequence[Any]) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in out:
            continue
        out.append(normalized)
    return out


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _decimal_json(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def _round_float(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}
