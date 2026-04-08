"""Settlement-Pipeline Zustandslogik (Prompt 16)."""

from __future__ import annotations

import pytest

from shared_py.settlement_pipeline import (
    assert_transition_allowed,
    initial_status,
    is_terminal_status,
    next_status,
)


def test_initial_status_secondary() -> None:
    assert initial_status(secondary_treasury_approval_required=True) == "pending_treasury"
    assert initial_status(secondary_treasury_approval_required=False) == "approved_for_payout"


def test_happy_path_transitions() -> None:
    assert next_status("pending_treasury", "treasury_approve") == "approved_for_payout"
    assert next_status("approved_for_payout", "record_payout") == "payout_recorded"
    assert next_status("payout_recorded", "confirm_settled") == "settled"


def test_terminal_detection() -> None:
    assert is_terminal_status("settled")
    assert is_terminal_status("cancelled")
    assert not is_terminal_status("approved_for_payout")


def test_invalid_transition() -> None:
    with pytest.raises(ValueError):
        assert_transition_allowed("payout_recorded", "treasury_approve")
