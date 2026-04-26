"""Sicherstellen, dass pytest faulthandler_timeout gesetzt ist (Diagnose bei Test-Haengern)."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_has_faulthandler_timeout() -> None:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    opts = data["tool"]["pytest"]["ini_options"]
    timeout = int(opts.get("faulthandler_timeout", 0))
    assert timeout >= 60, "faulthandler_timeout fehlt oder ist zu klein (Haenger-Diagnose)"
