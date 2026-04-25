from __future__ import annotations

from shared_py.readiness_scorecard import REQUIRED_CATEGORIES, build_readiness_scorecard


def _matrix(status: str = "verified", overrides: dict[str, str] | None = None) -> dict[str, object]:
    overrides = overrides or {}
    return {
        "categories": [
            {
                "id": category_id,
                "title": title,
                "status": overrides.get(category_id, status),
                "severity": "P0",
                "blocks_live_trading": category_id != "private_owner_scope",
                "next_action": f"{category_id} evidence.",
            }
            for category_id, title in REQUIRED_CATEGORIES
        ]
    }


def _mode(scorecard, mode: str) -> str:
    return next(item.decision for item in scorecard.mode_decisions if item.mode == mode)


def _all_reports() -> list[str]:
    return [
        "bitget_readiness.md",
        "dr_restore_test.md",
        "shadow_burn_in.md",
        "live_safety_drill.md",
        "production_readiness_scorecard.md",
    ]


def test_missing_restore_blocks_private_live_allowed() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"backup_restore": "partial"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"
    assert any("backup_restore" in item for item in scorecard.live_blockers)


def test_missing_shadow_burn_in_blocks_private_live_allowed() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"shadow_burn_in": "external_required"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


def test_missing_bitget_readiness_blocks_private_live_allowed() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"bitget_exchange_readiness": "external_required"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


def test_missing_asset_data_quality_blocks_live_for_asset() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=False,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"
    assert "asset_data_quality_for_concrete_assets_missing" in scorecard.asset_blockers


def test_full_autonomous_live_remains_no_go() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
    )
    assert _mode(scorecard, "full_autonomous_live") == "NO_GO"


def test_paper_can_go_when_no_live_danger() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"bitget_exchange_readiness": "external_required"}),
        report_names=[],
        asset_data_quality_verified=False,
    )
    assert _mode(scorecard, "paper") == "GO"


def test_shadow_can_go_with_warnings() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(status="partial", overrides={"private_owner_scope": "verified"}),
        report_names=[],
        asset_data_quality_verified=False,
    )
    assert _mode(scorecard, "shadow") == "GO_WITH_WARNINGS"
