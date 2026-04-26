from __future__ import annotations

from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety


def test_submit_timeout_sets_unknown_and_never_success() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-timeout", "idem-timeout", "cid-timeout", set(), "submit_prepared", "timeout")
    )
    assert state == "unknown_submit_state"
    assert "submit_timeout_unknown_state" in reasons
