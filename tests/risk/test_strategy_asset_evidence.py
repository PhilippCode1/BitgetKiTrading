from __future__ import annotations

from shared_py.strategy_asset_evidence import (
    StrategyAssetEvidence,
    build_strategy_asset_evidence_summary_de,
    strategy_evidence_blocks_live,
    validate_strategy_asset_evidence,
)


def _base(**overrides: object) -> StrategyAssetEvidence:
    payload = {
        "strategy_id": "trend_follow_v2",
        "strategy_version": "2.3.1",
        "playbook_id": "playbook_main",
        "asset_symbol": "BTCUSDT",
        "asset_class": "top_liquid_futures",
        "market_family": "futures",
        "risk_tier": "RISK_TIER_1_MAJOR_LIQUID",
        "data_quality_status": "data_ok",
        "evidence_status": "shadow_passed",
        "backtest_available": True,
        "walk_forward_available": True,
        "paper_available": True,
        "shadow_available": True,
        "shadow_passed": True,
        "expires_at": "2027-01-01T00:00:00Z",
        "fees_included": True,
        "spread_included": True,
        "slippage_included": True,
        "funding_included": True,
        "max_drawdown": 0.12,
        "number_of_trades": 42,
        "profit_factor": 1.35,
        "out_of_sample_result": "passed",
        "walk_forward_result": "passed",
        "paper_result": "passed",
        "shadow_result": "passed",
        "market_phases_tested": ["trend", "range"],
        "longest_loss_streak": 4,
        "risk_per_trade": 0.01,
        "parameter_hash": "sha256:test-hash",
        "model_parameters_reproducible": True,
        "evidence_level": "shadow",
        "checked_at": "2026-01-01T00:00:00Z",
        "git_sha": "deadbeef",
        "scope_asset_symbols": ["BTCUSDT"],
        "scope_asset_classes": ["top_liquid_futures"],
        "allowed_market_families": ["futures"],
        "allowed_risk_tiers": ["RISK_TIER_1_MAJOR_LIQUID", "RISK_TIER_2_LIQUID"],
    }
    payload.update(overrides)
    return StrategyAssetEvidence(**payload)  # type: ignore[arg-type]


def test_missing_evidence_blocks_live() -> None:
    e = _base(evidence_status="missing")
    assert strategy_evidence_blocks_live(e) is True


def test_backtest_only_blocks_live() -> None:
    e = _base(evidence_status="backtest_available", shadow_available=False, shadow_passed=False)
    assert "evidence_status_nicht_live_faehig" in validate_strategy_asset_evidence(e)


def test_paper_only_blocks_live() -> None:
    e = _base(evidence_status="paper_available", shadow_available=False, shadow_passed=False)
    assert strategy_evidence_blocks_live(e) is True


def test_shadow_passed_allows_candidate_not_auto_live() -> None:
    e = _base(evidence_status="shadow_passed")
    assert strategy_evidence_blocks_live(e) is False


def test_rejected_blocks() -> None:
    e = _base(evidence_status="rejected")
    assert "strategy_evidence_rejected" in validate_strategy_asset_evidence(e)


def test_expired_blocks() -> None:
    e = _base(expires_at="2024-01-01T00:00:00Z")
    assert "strategy_evidence_expired" in validate_strategy_asset_evidence(e)


def test_market_family_mismatch_blocks() -> None:
    e = _base(market_family="spot", allowed_market_families=["futures"])
    assert "market_family_mismatch" in validate_strategy_asset_evidence(e)


def test_risk_tier_mismatch_blocks() -> None:
    e = _base(risk_tier="RISK_TIER_3_ELEVATED_RISK")
    assert "risk_tier_mismatch" in validate_strategy_asset_evidence(e)


def test_unknown_asset_class_blocks() -> None:
    e = _base(asset_class="unknown", scope_asset_symbols=[], scope_asset_classes=[])
    assert "asset_class_unknown" in validate_strategy_asset_evidence(e)


def test_missing_strategy_version_blocks() -> None:
    e = _base(strategy_version=None)
    assert "strategy_version_fehlt" in validate_strategy_asset_evidence(e)


def test_summary_is_german() -> None:
    e = _base(evidence_status="missing")
    text = build_strategy_asset_evidence_summary_de(e)
    assert "blockiert" in text


def test_pass_is_only_next_gate_step_not_auto_order() -> None:
    e = _base(evidence_status="shadow_passed")
    text = build_strategy_asset_evidence_summary_de(e)
    assert "naechsten Gate-Schritt" in text
