"""Release-Sanity: operative Owner-Freigabe-Datei darf nicht git-getrackt sein."""

from __future__ import annotations

from pathlib import Path

from tools.release_sanity_checks import owner_private_live_release_tracked_by_git

ROOT = Path(__file__).resolve().parents[2]


def test_owner_release_not_tracked_in_real_repo() -> None:
    assert owner_private_live_release_tracked_by_git(ROOT) is None


def test_owner_release_tracked_is_error(monkeypatch) -> None:
    class _R:
        returncode = 0
        stdout = "reports/owner_private_live_release.json\n"

    monkeypatch.setattr(
        "tools.release_sanity_checks.subprocess.run",
        lambda *_a, **_k: _R(),
    )
    hit = owner_private_live_release_tracked_by_git(ROOT)
    assert hit is not None
    assert hit[0] == "ERROR"
    assert "Git-Index" in hit[1]
