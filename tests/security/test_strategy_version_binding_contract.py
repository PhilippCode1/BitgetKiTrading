from __future__ import annotations

from shared_py.strategy_asset_evidence import StrategyAssetEvidence, validate_strategy_asset_evidence


def test_strategy_version_without_hash_blocks_live_contract() -> None:
    item = StrategyAssetEvidence(
        strategy_id="s",
        strategy_version="1.0.0",
        playbook_id="pb",
        asset_symbol="BTCUSDT",
        asset_class="top_liquid_futures",
        market_family="futures",
        risk_tier="RISK_TIER_1_MAJOR_LIQUID",
        data_quality_status="data_ok",
        evidence_status="shadow_passed",
        backtest_available=True,
        walk_forward_available=True,
        paper_available=True,
        shadow_available=True,
        shadow_passed=True,
        expires_at=None,
        scope_asset_symbols=["BTCUSDT"],
        scope_asset_classes=["top_liquid_futures"],
        allowed_market_families=["futures"],
        allowed_risk_tiers=["RISK_TIER_1_MAJOR_LIQUID"],
        fees_included=True,
        spread_included=True,
        slippage_included=True,
        funding_included=True,
        risk_per_trade=0.01,
        number_of_trades=100,
        profit_factor=1.2,
        max_drawdown=0.1,
        longest_loss_streak=3,
        out_of_sample_result="passed",
        walk_forward_result="passed",
        paper_result="passed",
        shadow_result="passed",
        market_phases_tested=["trend", "range"],
        parameter_hash=None,
        model_parameters_reproducible=False,
        evidence_level="shadow",
        checked_at="2026-04-26T10:00:00Z",
        git_sha="abc1234",
    )
    reasons = validate_strategy_asset_evidence(item)
    assert "parameter_hash_fehlt" in reasons
    assert "parameter_nicht_reproduzierbar" in reasons
