"""Invarianten: private_live/full_autonomous bleiben hart fail-closed."""

from __future__ import annotations

from shared_py.readiness_scorecard import (
    PRIVATE_LIVE_REQUIRED_VERIFIED,
    REQUIRED_CATEGORIES,
    build_readiness_scorecard,
)


def test_private_live_required_subset_of_declared_categories() -> None:
    declared = {cid for cid, _ in REQUIRED_CATEGORIES}
    orphan = PRIVATE_LIVE_REQUIRED_VERIFIED - declared
    assert not orphan, (
        "PRIVATE_LIVE_REQUIRED_VERIFIED enthaelt IDs, die nicht in "
        f"REQUIRED_CATEGORIES vorkommen (Drift): {sorted(orphan)}"
    )


def test_private_live_required_nonempty() -> None:
    assert len(PRIVATE_LIVE_REQUIRED_VERIFIED) >= 5


def test_full_autonomous_live_is_always_no_go_even_when_everything_verified() -> None:
    matrix = {
        "categories": [
            {
                "id": cid,
                "title": title,
                "status": "verified",
                "severity": "P0",
                "blocks_live_trading": cid != "private_owner_scope",
                "next_action": "none",
            }
            for cid, title in REQUIRED_CATEGORIES
        ]
    }
    scorecard = build_readiness_scorecard(
        matrix,
        report_names=[
            "bitget_readiness.md",
            "dr_restore_test.md",
            "shadow_burn_in.md",
            "live_safety_drill.md",
            "branch_protection_ci_evidence.md",
            "asset_preflight_evidence.md",
            "production_readiness_scorecard.md",
        ],
        asset_data_quality_verified=True,
        owner_private_live_release_confirmed=True,
    )
    decision = next(item for item in scorecard.mode_decisions if item.mode == "full_autonomous_live")
    assert decision.decision == "NO_GO"


def test_private_live_required_contains_hard_runtime_categories() -> None:
    required = {
        "bitget_exchange_readiness",
        "backup_restore",
        "shadow_burn_in",
        "emergency_flatten",
        "order_idempotency",
        "reconcile_safety",
        "kill_switch_safety_latch",
        "final_go_no_go_scorecard",
    }
    assert required.issubset(PRIVATE_LIVE_REQUIRED_VERIFIED)
