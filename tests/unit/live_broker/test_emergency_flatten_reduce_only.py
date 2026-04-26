from __future__ import annotations

from shared_py.main_console_safety import emergency_flatten_is_reduce_only


def test_emergency_flatten_is_reduce_only() -> None:
    assert emergency_flatten_is_reduce_only(reduce_only=True, requested_qty=0.5, position_qty=1.0) is True
    assert emergency_flatten_is_reduce_only(reduce_only=False, requested_qty=0.5, position_qty=1.0) is False
