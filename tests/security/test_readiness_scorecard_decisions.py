from __future__ import annotations

from shared_py.readiness_scorecard import (
    REQUIRED_CATEGORIES,
    asset_preflight_fixture_evidence_ok,
    build_readiness_scorecard,
    owner_private_live_release_payload_ok,
)


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
        "branch_protection_ci_evidence.md",
        "asset_preflight_evidence.md",
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


def test_any_single_p0_not_verified_blocks_private_live_allowed() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"order_idempotency": "implemented"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"
    assert any("order_idempotency_not_verified" in item for item in scorecard.private_live_blockers)


def test_implemented_never_counts_like_verified() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"live_broker_fail_closed": "implemented"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    category = next(item for item in scorecard.categories if item.id == "live_broker_fail_closed")
    assert category.decision == "NOT_ENOUGH_EVIDENCE"
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


def test_external_required_never_counts_like_verified() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"backup_restore": "external_required"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    category = next(item for item in scorecard.categories if item.id == "backup_restore")
    assert category.decision == "EXTERNAL_REQUIRED"
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


def test_branch_protection_only_implemented_keeps_private_live_no_go() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(overrides={"branch_protection_ci": "implemented"}),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"
    assert any("branch_protection_ci_not_verified" in item for item in scorecard.private_live_blockers)


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


def test_asset_preflight_fixture_evidence_clears_generic_concrete_asset_gap() -> None:
    payload = {
        "assets_checked": 1,
        "live_allowed_count": 0,
        "private_live_decision": "NO_GO",
        "assets": [
            {
                "symbol": "BTCUSDT",
                "live_preflight_status": "LIVE_BLOCKED",
                "block_reasons": ["owner_approval_missing"],
            }
        ],
    }
    assert asset_preflight_fixture_evidence_ok({"asset_preflight_evidence": payload}) is True
    scorecard = build_readiness_scorecard(
        _matrix(status="partial", overrides={"private_owner_scope": "verified"}),
        report_names=["asset_preflight_evidence.md"],
        report_payloads={"asset_preflight_evidence": payload},
    )
    assert "asset_data_quality_for_concrete_assets_missing" not in scorecard.asset_blockers
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


def test_asset_preflight_evidence_never_counts_live_allowed_payload() -> None:
    payload = {
        "assets_checked": 1,
        "live_allowed_count": 1,
        "private_live_decision": "NO_GO",
        "assets": [
            {
                "symbol": "BTCUSDT",
                "live_preflight_status": "LIVE_ALLOWED",
                "block_reasons": [],
            }
        ],
    }
    assert asset_preflight_fixture_evidence_ok({"asset_preflight_evidence": payload}) is False


def test_full_autonomous_live_remains_no_go() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    assert _mode(scorecard, "full_autonomous_live") == "NO_GO"


def test_perfect_matrix_without_owner_release_file_blocks_private_live() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=False,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"
    assert "owner_private_live_release:not_confirmed" in scorecard.private_live_blockers


def test_perfect_matrix_with_owner_release_allows_private_live() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "GO"
    assert "owner_private_live_release:not_confirmed" not in scorecard.private_live_blockers


def test_owner_release_payload_rejects_false_go() -> None:
    assert (
        owner_private_live_release_payload_ok(
            {"owner_private_live_go": False, "recorded_at": "2026-01-01T00:00:00Z", "signoff_reference": "x" * 8}
        )
        is False
    )


def test_owner_release_payload_requires_reference_length() -> None:
    assert (
        owner_private_live_release_payload_ok(
            {"owner_private_live_go": True, "recorded_at": "2026-01-01T00:00:00Z", "signoff_reference": "short"}
        )
        is False
    )


def test_owner_release_payload_accepts_valid() -> None:
    assert (
        owner_private_live_release_payload_ok(
            {
                "owner_private_live_go": True,
                "recorded_at": "2026-04-26T12:00:00Z",
                "signoff_reference": "audit_ticket_ABCDEF12",
            }
        )
        is True
    )


def test_implemented_and_external_required_never_upgrade_to_go() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(
            overrides={
                "bitget_exchange_readiness": "external_required",
                "reconcile_safety": "implemented",
            }
        ),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    assert _mode(scorecard, "private_live_allowed") == "NO_GO"


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
