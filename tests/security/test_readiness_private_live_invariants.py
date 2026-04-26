"""Invarianten: Private-Live-Pflichtkategorien duerfen nicht aus der Scorecard-Liste herausfallen."""

from __future__ import annotations

from shared_py.readiness_scorecard import PRIVATE_LIVE_REQUIRED_VERIFIED, REQUIRED_CATEGORIES


def test_private_live_required_subset_of_declared_categories() -> None:
    declared = {cid for cid, _ in REQUIRED_CATEGORIES}
    orphan = PRIVATE_LIVE_REQUIRED_VERIFIED - declared
    assert not orphan, (
        "PRIVATE_LIVE_REQUIRED_VERIFIED enthaelt IDs, die nicht in "
        f"REQUIRED_CATEGORIES vorkommen (Drift): {sorted(orphan)}"
    )


def test_private_live_required_nonempty() -> None:
    assert len(PRIVATE_LIVE_REQUIRED_VERIFIED) >= 5
