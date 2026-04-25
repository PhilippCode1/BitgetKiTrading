from __future__ import annotations

from shared_py.order_lifecycle import OrderSubmitContext, evaluate_submit_safety


def test_missing_execution_id_blocks_submit() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext(None, "idem-1", "cid-1", set(), "submit_prepared", "ack")
    )
    assert state == "blocked"
    assert "execution_id_fehlt" in reasons


def test_missing_idempotency_blocks_submit() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", None, None, set(), "submit_prepared", "ack")
    )
    assert state == "blocked"
    assert "idempotency_fehlt" in reasons


def test_timeout_yields_unknown_submit_state() -> None:
    state, _ = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-1", set(), "submit_prepared", "timeout")
    )
    assert state == "unknown_submit_state"


def test_unknown_submit_state_blocks_new_opening() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-1", set(), "unknown_submit_state", "ack")
    )
    assert state == "blocked"
    assert "unknown_submit_state_blockiert_neue_openings" in reasons


def test_retry_without_reconcile_blocks() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-1", set(), "reconcile_required", "ack")
    )
    assert state == "blocked"
    assert "retry_ohne_reconcile_verboten" in reasons


def test_duplicate_client_order_id_blocks() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-dup", {"cid-dup"}, "submit_prepared", "ack")
    )
    assert state == "blocked"
    assert "duplicate_client_order_id" in reasons


def test_exchange_reject_sets_rejected_failed_path() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-1", set(), "submit_prepared", "reject")
    )
    assert state == "exchange_rejected"
    assert "exchange_reject" in reasons


def test_db_failure_after_submit_sets_reconcile_required() -> None:
    state, reasons = evaluate_submit_safety(
        OrderSubmitContext("exec-1", "idem-1", "cid-1", set(), "submit_prepared", "db_failure_after_submit")
    )
    assert state == "reconcile_required"
    assert "db_failure_reconcile_required" in reasons
