from __future__ import annotations

from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety


def test_duplicate_client_oid_detected_and_blocked() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-dup", "idem-dup", "cid-dup", {"cid-dup"}, "submit_prepared", "ack")
    )
    assert state == "blocked"
    assert "duplicate_client_order_id" in reasons
