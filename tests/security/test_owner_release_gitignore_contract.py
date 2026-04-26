"""Contract: operative Owner-Freigabe darf nicht per Git-Tracking ins Repo gelangen."""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GITIGNORE = REPO / ".gitignore"
EXPECTED_LINE = "reports/owner_private_live_release.json"


def test_owner_private_live_release_is_gitignored() -> None:
    assert GITIGNORE.is_file(), f"fehlt {GITIGNORE}"
    lines = GITIGNORE.read_text(encoding="utf-8").splitlines()
    stripped = {ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")}
    assert EXPECTED_LINE in stripped, (
        f".gitignore muss `{EXPECTED_LINE}` enthalten (No-Go Regel 53 / release_sanity)."
    )
