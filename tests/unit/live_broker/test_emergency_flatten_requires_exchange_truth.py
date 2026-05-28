from __future__ import annotations

from shared_py.main_console_safety import (
    SafetyCenterSnapshot,
    live_blocked_by_safety_center,
)


def test_emergency_flatten_requires_exchange_truth_clean() -> None:
    blocked = live_blocked_by_safety_center(
        SafetyCenterSnapshot(
            reconcile_status="ok",
            kill_switch_active=False,
            safety_latch_active=False,
            exchange_truth_status="not_checked",
            backend_connected=True,
        )
    )
    assert blocked is True
