from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "secrets_rotation_drill.py"
SECRET_PATTERNS = (
    re.compile(r"sk-(?:proj|test|live)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


def test_drill_dry_run_works() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "secrets_rotation_drill: simulated" in result.stdout
    assert "raw_secret_values_included=false" in result.stdout


def test_report_contains_no_raw_secrets(tmp_path: Path) -> None:
    report = tmp_path / "secrets_rotation_drill.md"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "simulated",
            "--output-md",
            str(report),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    text = report.read_text(encoding="utf-8")
    assert "Raw secret values included: `false`" in text
    assert "BITGET_API_SECRET" not in text
    assert not any(pattern.search(text) for pattern in SECRET_PATTERNS)
