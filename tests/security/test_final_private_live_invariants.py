from __future__ import annotations

from scripts.final_go_no_go_report import build_payload


def test_private_live_allowed_stays_no_without_owner_signoff() -> None:
    payload = build_payload()
    assert payload["mode_decisions"]["private_live_allowed"] == "NO"
    assert "owner_private_live_release_missing" in payload["missing_owner_evidence"] or payload["missing_owner_evidence"]


def test_implemented_and_external_required_not_counted_as_verified() -> None:
    payload = build_payload()
    counts = payload["status_counts"]
    assert counts["implemented"] >= 1
    assert counts["external_required"] >= 1
    assert payload["mode_decisions"]["private_live_allowed"] == "NO"
