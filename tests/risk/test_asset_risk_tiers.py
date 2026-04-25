from __future__ import annotations

from shared_py.asset_risk_tiers import (
    asset_live_eligibility_reasons,
    asset_risk_tier_blocks_live,
    asset_tier_requires_owner_review,
    asset_tier_allows_mode,
    build_asset_risk_summary_de,
    classify_asset_risk_tier,
    classify_asset_risk_band,
    dynamic_max_leverage_for_asset,
    max_leverage_for_asset_tier,
)


def test_asset_without_risk_tier_blocks_live() -> None:
    reasons = asset_live_eligibility_reasons(
        tier=None,
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=True,
        owner_approved=True,
        account_context_fresh=True,
        spread_bps=2.0,
    )
    assert "asset_tier_missing" in reasons


def test_unknown_tier_blocks_live() -> None:
    reasons = asset_live_eligibility_reasons(
        tier="RISK_TIER_UNKNOWN",
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=True,
        owner_approved=True,
        account_context_fresh=True,
        spread_bps=2.0,
    )
    assert "asset_tier_unknown" in reasons
    band = classify_asset_risk_band(
        requested_tier="RISK_TIER_UNKNOWN",
        liquidity_tier="TIER_1",
        data_quality_status="data_ok",
        volatility_0_1=0.1,
        spread_bps=2.0,
        slippage_bps=5.0,
        strategy_evidence_ready=True,
    )
    assert band == "RISK_TIER_E"


def test_tier_0_blocks_live() -> None:
    reasons = asset_live_eligibility_reasons(
        tier="RISK_TIER_0_BLOCKED",
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=True,
        owner_approved=True,
        account_context_fresh=True,
        spread_bps=2.0,
    )
    assert "asset_tier_0_live_blocked" in reasons


def test_tier_4_blocks_live_and_allows_shadow_only() -> None:
    reasons = asset_live_eligibility_reasons(
        tier="RISK_TIER_4_SHADOW_ONLY",
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=True,
        owner_approved=True,
        account_context_fresh=True,
        spread_bps=2.0,
    )
    assert "asset_tier_4_shadow_only" in reasons
    assert asset_tier_allows_mode("RISK_TIER_4_SHADOW_ONLY", "shadow") is True
    assert asset_tier_allows_mode("RISK_TIER_4_SHADOW_ONLY", "live") is False


def test_tier_5_blocks_every_mode() -> None:
    assert asset_tier_allows_mode("RISK_TIER_5_BANNED_OR_DELISTED", "paper") is False
    assert asset_tier_allows_mode("RISK_TIER_5_BANNED_OR_DELISTED", "shadow") is False
    assert asset_tier_allows_mode("RISK_TIER_5_BANNED_OR_DELISTED", "live") is False
    assert asset_risk_tier_blocks_live("RISK_TIER_5_BANNED_OR_DELISTED") is True


def test_tier_1_requires_live_gates() -> None:
    reasons = asset_live_eligibility_reasons(
        tier="RISK_TIER_1_MAJOR_LIQUID",
        data_quality_status="data_stale",
        liquidity_status="yellow",
        strategy_evidence_ready=False,
        owner_approved=False,
        account_context_fresh=False,
        spread_bps=3.0,
    )
    assert "data_quality_not_green" in reasons
    assert "liquidity_not_green" in reasons
    assert "strategy_evidence_missing" in reasons
    assert "owner_approval_missing" in reasons
    assert "account_context_stale" in reasons


def test_high_volatility_downgrades_or_blocks() -> None:
    downgraded = classify_asset_risk_tier(
        requested_tier="RISK_TIER_1_MAJOR_LIQUID",
        volatility_0_1=0.70,
        spread_bps=4.0,
    )
    blocked = classify_asset_risk_tier(
        requested_tier="RISK_TIER_2_LIQUID",
        volatility_0_1=0.90,
        spread_bps=4.0,
    )
    assert downgraded == "RISK_TIER_2_LIQUID"
    assert blocked == "RISK_TIER_0_BLOCKED"
    assert dynamic_max_leverage_for_asset(
        tier="RISK_TIER_1_MAJOR_LIQUID",
        volatility_0_1=0.90,
        live_start_phase=False,
    ) < max_leverage_for_asset_tier("RISK_TIER_1_MAJOR_LIQUID")


def test_bad_spread_blocks() -> None:
    tier = classify_asset_risk_tier(
        requested_tier="RISK_TIER_1_MAJOR_LIQUID",
        volatility_0_1=0.20,
        spread_bps=180.0,
    )
    assert tier == "RISK_TIER_0_BLOCKED"


def test_high_slippage_and_bad_data_quality_downgrade_to_d_or_e() -> None:
    tier_d = classify_asset_risk_band(
        requested_tier="RISK_TIER_2_LIQUID",
        liquidity_tier="TIER_2",
        data_quality_status="data_stale",
        volatility_0_1=0.3,
        spread_bps=10.0,
        slippage_bps=20.0,
        strategy_evidence_ready=True,
    )
    tier_e = classify_asset_risk_band(
        requested_tier=None,
        liquidity_tier="TIER_5",
        data_quality_status="data_ok",
        volatility_0_1=0.2,
        spread_bps=10.0,
        slippage_bps=200.0,
        strategy_evidence_ready=False,
    )
    assert tier_d in {"RISK_TIER_D", "RISK_TIER_E"}
    assert tier_e == "RISK_TIER_E"


def test_tier_a_has_higher_cap_than_tier_c() -> None:
    assert max_leverage_for_asset_tier("RISK_TIER_1_MAJOR_LIQUID") > max_leverage_for_asset_tier(
        "RISK_TIER_3_ELEVATED_RISK"
    )


def test_tier_c_requires_owner_review_and_strategy_evidence() -> None:
    assert asset_tier_requires_owner_review("RISK_TIER_3_ELEVATED_RISK") is True
    reasons = asset_live_eligibility_reasons(
        tier="RISK_TIER_3_ELEVATED_RISK",
        data_quality_status="data_ok",
        liquidity_status="green",
        strategy_evidence_ready=False,
        owner_approved=False,
        account_context_fresh=True,
        spread_bps=5.0,
    )
    assert "strategy_evidence_missing" in reasons
    assert "tier_c_owner_review_required" in reasons


def test_risk_summary_is_german() -> None:
    summary = build_asset_risk_summary_de(
        symbol="BTCUSDT",
        tier="RISK_TIER_1_MAJOR_LIQUID",
        reasons=["kein_blocker"],
    )
    assert "Asset BTCUSDT" in summary
    assert "max Hebel" in summary
