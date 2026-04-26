from __future__ import annotations

from shared_py.strategy_asset_evidence import StrategyAssetEvidence, strategy_evidence_blocks_live


def _base() -> StrategyAssetEvidence:
    return StrategyAssetEvidence(
        strategy_id="trend_a",
        strategy_version="1.0.0",
        playbook_id="pb_trend",
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
        expires_at="2027-01-01T00:00:00Z",
        scope_asset_symbols=["BTCUSDT"],
        scope_asset_classes=["top_liquid_futures"],
        allowed_market_families=["futures"],
        allowed_risk_tiers=["RISK_TIER_1_MAJOR_LIQUID"],
        fees_included=True,
        spread_included=True,
        slippage_included=True,
        funding_included=True,
        risk_per_trade=0.01,
        number_of_trades=80,
        profit_factor=1.3,
        max_drawdown=0.12,
        longest_loss_streak=4,
        out_of_sample_result="passed",
        walk_forward_result="passed",
        paper_result="passed",
        shadow_result="passed",
        market_phases_tested=["trend", "range"],
        parameter_hash="sha256:abc",
        model_parameters_reproducible=True,
        evidence_level="shadow",
        checked_at="2026-04-26T10:00:00Z",
        git_sha="abc1234",
    )


def test_strategy_without_evidence_blocks_live() -> None:
    item = _base()
    item = StrategyAssetEvidence(**{**item.__dict__, "evidence_status": "missing"})
    assert strategy_evidence_blocks_live(item) is True


def test_missing_cost_components_or_drawdown_blocks_live() -> None:
    base = _base()
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "fees_included": False})) is True
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "slippage_included": False})) is True
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "max_drawdown": None})) is True


def test_missing_oos_or_paper_shadow_or_too_few_trades_blocks_live() -> None:
    base = _base()
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "number_of_trades": 5})) is True
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "out_of_sample_result": "missing"})) is True
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "paper_result": "missing"})) is True
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "shadow_result": "missing"})) is True


def test_futures_without_funding_and_synthetic_evidence_never_verified() -> None:
    base = _base()
    assert strategy_evidence_blocks_live(StrategyAssetEvidence(**{**base.__dict__, "funding_included": False})) is True
    assert strategy_evidence_blocks_live(
        StrategyAssetEvidence(**{**base.__dict__, "evidence_level": "synthetic", "profit_factor": 1.8})
    ) is True
