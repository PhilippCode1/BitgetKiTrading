from __future__ import annotations

from shared_py.main_console_safety import emergency_flatten_is_reduce_only


def test_live_safety_action_never_increases_risk() -> None:
    assert emergency_flatten_is_reduce_only(reduce_only=True, requested_qty=1.5, position_qty=1.0) is False
    assert emergency_flatten_is_reduce_only(reduce_only=True, requested_qty=0.5, position_qty=1.0) is True
