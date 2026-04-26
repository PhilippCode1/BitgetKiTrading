from __future__ import annotations

from shared_py.leverage_allocator import allocate_integer_leverage


def test_burn_in_cap_7_blocks_higher_requested_leverage() -> None:
    out = allocate_integer_leverage(
        requested_leverage=25,
        caps={"risk_allowed": 7, "live_ramp": 7},
    )
    assert out["allowed_leverage"] == 7
    assert out["recommended_leverage"] == 7


def test_unknown_requested_leverage_is_capped_conservatively() -> None:
    out = allocate_integer_leverage(
        requested_leverage=None,
        caps={"risk_allowed": 7},
    )
    assert out["allowed_leverage"] == 7
