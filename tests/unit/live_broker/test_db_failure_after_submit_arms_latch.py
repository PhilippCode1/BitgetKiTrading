from __future__ import annotations

from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety


def test_db_failure_after_submit_requires_reconcile_path() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-db", "idem-db", "cid-db", set(), "submit_prepared", "db_failure_after_submit")
    )
    assert state == "reconcile_required"
    assert "db_failure_reconcile_required" in reasons
