from __future__ import annotations

from shared_py.asset_risk_tiers import (
    asset_risk_tier_blocks_live,
    build_asset_risk_audit_payload,
    classify_asset_risk_band,
    max_notional_for_asset_tier,
    validate_multi_asset_order_sizing,
)


def test_unknown_asset_is_tier_e_or_blocked() -> None:
    band = classify_asset_risk_band(
        requested_tier=None,
        liquidity_tier="TIER_3",
        data_quality_status="data_ok",
        volatility_0_1=0.2,
        spread_bps=5.0,
        slippage_bps=5.0,
        strategy_evidence_ready=False,
    )
    assert band == "RISK_TIER_E"
    assert asset_risk_tier_blocks_live(None) is True


def test_delisted_and_suspended_are_tier_e() -> None:
    delisted = classify_asset_risk_band(
        requested_tier="RISK_TIER_1_MAJOR_LIQUID",
        liquidity_tier="TIER_1",
        data_quality_status="data_ok",
        volatility_0_1=0.2,
        spread_bps=4.0,
        slippage_bps=5.0,
        delisted=True,
        strategy_evidence_ready=True,
    )
    suspended = classify_asset_risk_band(
        requested_tier="RISK_TIER_1_MAJOR_LIQUID",
        liquidity_tier="TIER_1",
        data_quality_status="data_ok",
        volatility_0_1=0.2,
        spread_bps=4.0,
        slippage_bps=5.0,
        suspended=True,
        strategy_evidence_ready=True,
    )
    assert delisted == "RISK_TIER_E"
    assert suspended == "RISK_TIER_E"


def test_audit_payload_contains_tier_and_reasons() -> None:
    payload = build_asset_risk_audit_payload(
        symbol="SOLUSDT",
        tier="RISK_TIER_3_ELEVATED_RISK",
        mode="live",
        reasons=["strategy_evidence_missing", "owner_approval_missing"],
    )
    assert payload["tier"] == "RISK_TIER_3_ELEVATED_RISK"
    assert payload["risk_band"] in {"RISK_TIER_C", "RISK_TIER_D", "RISK_TIER_E"}
    assert len(payload["reasons"]) >= 1


def test_no_tier_sets_live_allowed_automatically_true() -> None:
    out = validate_multi_asset_order_sizing(
        symbol="BTCUSDT",
        tier="RISK_TIER_1_MAJOR_LIQUID",
        mode="live",
        requested_leverage=1,
        requested_notional_usdt=max_notional_for_asset_tier("RISK_TIER_1_MAJOR_LIQUID") + 1.0,
    )
    assert out["valid"] is False
    assert "position_notional_above_tier_cap" in out["reasons"]
