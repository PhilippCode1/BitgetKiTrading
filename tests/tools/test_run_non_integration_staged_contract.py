"""Kontrakttests fuer tools/run_non_integration_staged.py (ohne vollstaendigen Pytest-Lauf)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS = REPO_ROOT / "tools" / "run_non_integration_staged.py"


def _load_staged() -> object:
    spec = importlib.util.spec_from_file_location("run_non_integration_staged", TOOLS)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


def test_staged_module_defines_four_paths() -> None:
    m = _load_staged()
    assert len(m.STAGES) == 4  # type: ignore[attr-defined]
    assert m.STAGES[0][0] == "shared_python"  # type: ignore[attr-defined]
    assert m.STAGES[2][1] == ["tests", "--ignore=tests/unit"]  # type: ignore[attr-defined]
    assert m.STAGES[3][1] == ["tests/unit"]  # type: ignore[attr-defined]


def test_onchain_test_dir_exists() -> None:
    assert (REPO_ROOT / "services" / "onchain-sniffer" / "tests").is_dir()


def test_staged_pytest_root_dirs_exist() -> None:
    """Jede Stufe muss auf ein existierendes Test-Verzeichnis zeigen (keine toten Pfade)."""
    m = _load_staged()
    for _label, spec in m.STAGES:  # type: ignore[attr-defined]
        for part in spec:
            if part.startswith("-"):
                continue
            path = REPO_ROOT / part
            assert path.is_dir(), f"fehlt Testpfad fuer Staged-Pytest: {part}"


def test_main_short_circuits_on_first_nonzero() -> None:
    m = _load_staged()
    with patch.object(m, "_run_pytest", return_value=1) as mock_run:  # type: ignore[arg-type]
        rc = m.main([])  # type: ignore[attr-defined]
        assert rc == 1
        assert mock_run.call_count == 1
