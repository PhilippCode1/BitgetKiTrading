from __future__ import annotations

from decimal import Decimal

from shared_py.bitget.execution_guards import reduce_only_position_consistency_reasons


def test_reduce_only_without_exchange_position_blocks() -> None:
    reasons = reduce_only_position_consistency_reasons(
        reduce_only=True,
        order_side="sell",
        position_net_base=None,
        require_known_position=True,
    )
    assert reasons
    reasons_no_pos = reduce_only_position_consistency_reasons(
        reduce_only=True,
        order_side="sell",
        position_net_base=Decimal("0"),
        require_known_position=True,
    )
    assert "execution_guard_no_position_for_reduce_only" in reasons_no_pos
