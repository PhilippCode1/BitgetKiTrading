from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared_py.risk_engine import (
    TradeRiskLimits,
    evaluate_asset_tier_risk_gate,
    evaluate_trade_risk,
)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class GateConfig:
    min_strength: int
    min_prob: float
    min_risk_score: int
    min_expected_return_bps: float = 0.0
    max_expected_mae_bps: float = float("inf")
    min_projected_rr: float = 0.0


def should_auto_trade(signal: dict[str, Any], cfg: GateConfig) -> tuple[bool, list[str]]:
    decision = evaluate_trade_risk(
        signal=signal,
        limits=TradeRiskLimits(
            min_signal_strength=cfg.min_strength,
            min_probability=cfg.min_prob,
            min_risk_score=cfg.min_risk_score,
            min_expected_return_bps=cfg.min_expected_return_bps,
            max_expected_mae_bps=cfg.max_expected_mae_bps,
            min_projected_rr=cfg.min_projected_rr,
            min_allowed_leverage=7,
            max_position_risk_pct=1.0,
            max_account_margin_usage=1.0,
            max_account_drawdown_pct=1.0,
            max_daily_drawdown_pct=1.0,
            max_weekly_drawdown_pct=1.0,
            max_daily_loss_usdt=1_000_000_000.0,
            max_position_notional_usdt=1_000_000_000.0,
            max_concurrent_positions=1_000_000,
        ),
    )
    reasons = list(decision["reasons_json"])
    asset_gate = evaluate_asset_tier_risk_gate(
        symbol=str(signal.get("symbol") or signal.get("asset") or "UNKNOWN"),
        mode="paper",
        requested_tier=(
            str(signal.get("asset_risk_tier") or signal.get("asset_tier"))
            if signal.get("asset_risk_tier") is not None or signal.get("asset_tier") is not None
            else None
        ),
        volatility_0_1=_to_float(signal.get("asset_volatility_0_1") or signal.get("volatility_0_1"), 0.0),
        spread_bps=_to_float(signal.get("spread_bps"), 0.0),
        data_quality_status=str(signal.get("asset_data_quality_status") or "data_unknown"),
        liquidity_status=str(signal.get("asset_liquidity_status") or "unknown"),
        strategy_evidence_ready=bool(signal.get("strategy_evidence_ready")),
        owner_approved=bool(signal.get("owner_approved")),
        account_context_fresh=bool(signal.get("account_context_fresh")),
        requested_leverage=_to_int(signal.get("recommended_leverage") or signal.get("allowed_leverage"), 1),
        requested_notional_usdt=_to_float(signal.get("proposed_notional_usdt"), 0.0),
        delisted=bool(signal.get("asset_delisted")),
        suspended=bool(signal.get("asset_suspended")),
    )
    if asset_gate.get("blocked"):
        reasons.extend(f"asset_risk:{reason}" for reason in asset_gate.get("reasons_json", []))
        reasons = list(dict.fromkeys(reasons))
    return (len(reasons) == 0, reasons)


def direction_to_side(direction: str) -> str | None:
    d = direction.strip().lower()
    if d in ("long", "short"):
        return d
    return None


def warnung_against_position(signal: dict[str, Any], open_side: str | None) -> bool:
    if str(signal.get("signal_class", "")).lower() != "warnung":
        return False
    if open_side is None:
        return False
    d = direction_to_side(str(signal.get("direction", "neutral")))
    if d is None or d == "neutral":
        return False
    return d != open_side
