from __future__ import annotations

from shared_py.leverage_allocator import allocate_integer_leverage


def test_live_ramp_blocks_high_leverage_above_7() -> None:
    out = allocate_integer_leverage(
        requested_leverage=50,
        caps={"risk_allowed_leverage_max": 7, "risk_governor_live_ramp_max_leverage": 7},
    )
    assert out["allowed_leverage"] == 7
    assert out["recommended_leverage"] == 7
