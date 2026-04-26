from __future__ import annotations

from shared_py.main_console_safety import emergency_flatten_is_reduce_only


def test_emergency_flatten_flat_position_is_safe_noop() -> None:
    # Flat position => kein riskanter Flatten erlaubt, ergo fail-closed no-op.
    assert emergency_flatten_is_reduce_only(reduce_only=True, requested_qty=0.4, position_qty=0.0) is False
