from __future__ import annotations

from shared_py.strategy_asset_evidence import StrategyAssetEvidence, strategy_evidence_blocks_live


def _evidence(**overrides: object) -> StrategyAssetEvidence:
    base = {
        "strategy_id": "mr_v1",
        "strategy_version": "1.0.0",
        "playbook_id": "playbook_mr",
        "asset_symbol": "ETHUSDT",
        "asset_class": "major_spot",
        "market_family": "spot",
        "risk_tier": "RISK_TIER_2_LIQUID",
        "data_quality_status": "data_ok",
        "evidence_status": "shadow_passed",
        "backtest_available": True,
        "walk_forward_available": True,
        "paper_available": True,
        "shadow_available": True,
        "shadow_passed": True,
        "expires_at": "2027-01-01T00:00:00Z",
        "scope_asset_symbols": ["ETHUSDT"],
        "scope_asset_classes": ["major_spot"],
        "allowed_market_families": ["spot"],
        "allowed_risk_tiers": ["RISK_TIER_2_LIQUID"],
    }
    base.update(overrides)
    return StrategyAssetEvidence(**base)  # type: ignore[arg-type]


def test_live_scope_blocks_unknown_class() -> None:
    e = _evidence(asset_class="unknown", scope_asset_symbols=[], scope_asset_classes=[])
    assert strategy_evidence_blocks_live(e) is True


def test_live_scope_blocks_missing_strategy_metadata() -> None:
    e = _evidence(strategy_id=None, strategy_version=None, playbook_id=None)
    assert strategy_evidence_blocks_live(e) is True
