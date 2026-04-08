from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "filename,profile,expect_fail",
    [
        (".env.production", "local", True),
        (".env.shadow", "local", True),
        (".env.local", "local", False),
    ],
)
def test_profile_matches_env_filename(
    tmp_path: Path, filename: str, profile: str, expect_fail: bool
) -> None:
    p = tmp_path / filename
    p.write_text("POSTGRES_PASSWORD=x\n", encoding="utf-8")
    cmd = [
        sys.executable,
        str(REPO / "tools" / "validate_env_profile.py"),
        "--env-file",
        str(p),
        "--profile",
        profile,
    ]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True, check=False)
    if expect_fail:
        assert r.returncode == 1
        assert "widerspricht" in (r.stderr or "")
    else:
        # fehlt noch fast alles — erwarte Fehler wegen Platzhaltern, nicht wegen Namens-Mismatch
        assert "widerspricht" not in (r.stderr or "")
