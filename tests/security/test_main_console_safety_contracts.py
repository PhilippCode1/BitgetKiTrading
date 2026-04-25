from __future__ import annotations

from pathlib import Path

from shared_py.main_console_safety import (
    SafetyCenterSnapshot,
    contains_secret_like_text,
    emergency_flatten_is_reduce_only,
    live_blocked_by_safety_center,
)


def test_unknown_reconcile_blocks_live() -> None:
    snap = SafetyCenterSnapshot("unknown", False, False, "vorhanden", True)
    assert live_blocked_by_safety_center(snap) is True


def test_active_kill_switch_blocks_live() -> None:
    snap = SafetyCenterSnapshot("ok", True, False, "vorhanden", True)
    assert live_blocked_by_safety_center(snap) is True


def test_active_safety_latch_blocks_normal_orders() -> None:
    snap = SafetyCenterSnapshot("ok", False, True, "vorhanden", True)
    assert live_blocked_by_safety_center(snap) is True


def test_missing_exchange_truth_blocks_live() -> None:
    snap = SafetyCenterSnapshot("ok", False, False, "fehlt", True)
    assert live_blocked_by_safety_center(snap) is True


def test_emergency_flatten_is_reduce_only_safe_modeled() -> None:
    assert emergency_flatten_is_reduce_only(reduce_only=True, requested_qty=1.0, position_qty=2.0) is True
    assert emergency_flatten_is_reduce_only(reduce_only=False, requested_qty=1.0, position_qty=2.0) is False


def test_ui_payload_contains_no_secrets_and_labels_are_german() -> None:
    page = Path(
        "apps/dashboard/src/app/(operator)/console/safety-center/page.tsx"
    ).read_text(encoding="utf-8")
    assert contains_secret_like_text(page) is False
    for label in (
        "Sicherheitszentrale",
        "Kill-Switch",
        "Safety-Latch",
        "Nicht handelbar",
        "Notfallaktionen",
    ):
        assert label in page


def test_missing_backend_data_not_green() -> None:
    page = Path(
        "apps/dashboard/src/app/(operator)/console/safety-center/page.tsx"
    ).read_text(encoding="utf-8")
    assert "nicht geprüft" in page
