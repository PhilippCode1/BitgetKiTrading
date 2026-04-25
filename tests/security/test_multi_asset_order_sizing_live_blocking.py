from __future__ import annotations

from shared_py.asset_risk_tiers import (
    build_asset_risk_audit_payload,
    validate_multi_asset_order_sizing,
)
from shared_py.risk_engine import evaluate_asset_tier_risk_gate


def test_leverage_over_tier_cap_is_live_blocked() -> None:
    out = validate_multi_asset_order_sizing(
        symbol="BTCUSDT",
        tier="RISK_TIER_2_LIQUID",
        mode="live",
        requested_leverage=40,
        requested_notional_usdt=1000.0,
    )
    assert out["valid"] is False
    assert "leverage_above_tier_cap_live_blocked" in out["reasons"]


def test_notional_over_tier_cap_is_blocked() -> None:
    out = validate_multi_asset_order_sizing(
        symbol="SOLUSDT",
        tier="RISK_TIER_3_ELEVATED_RISK",
        mode="live",
        requested_leverage=4,
        requested_notional_usdt=10_000.0,
    )
    assert out["valid"] is False
    assert "position_notional_above_tier_cap" in out["reasons"]


def test_missing_account_snapshot_blocks_live() -> None:
    out = evaluate_asset_tier_risk_gate(
        symbol="ETHUSDT",
        mode="live",
        requested_tier="RISK_TIER_1_MAJOR_LIQUID",
        volatility_0_1=0.2,
        spread_bps=3.0,
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=True,
        owner_approved=True,
        account_context_fresh=False,
        requested_leverage=3,
        requested_notional_usdt=1000.0,
    )
    assert out["blocked"] is True
    assert "account_context_stale" in out["reasons_json"]


def test_audit_payload_contains_symbol_tier_and_reasons() -> None:
    reasons = ["asset_tier_0_live_blocked", "spread_too_wide"]
    payload = build_asset_risk_audit_payload(
        symbol="XRPUSDT",
        tier="RISK_TIER_0_BLOCKED",
        mode="live",
        reasons=reasons,
    )
    assert payload["symbol"] == "XRPUSDT"
    assert payload["tier"] == "RISK_TIER_0_BLOCKED"
    assert payload["reasons"] == reasons
