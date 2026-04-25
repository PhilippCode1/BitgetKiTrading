from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_secret_lifecycle import build_summary, run_checks


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_secret_lifecycle.py"


REQUIRED_FILES = (
    "docs/production_10_10/secrets_rotation_and_credential_hygiene.md",
    "docs/production_10_10/secrets_rotation_report_template.md",
    "scripts/secrets_rotation_drill.py",
    "shared/python/src/shared_py/secret_lifecycle.py",
    "tests/scripts/test_secrets_rotation_drill.py",
    "tests/security/test_secret_lifecycle_policy.py",
    "tests/tools/test_check_secret_lifecycle.py",
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _valid_fixture(root: Path) -> None:
    for rel in REQUIRED_FILES:
        _write(root / rel, "placeholder without raw secrets\n")
    _write(
        root / "docs/production_10_10/evidence_matrix.md",
        "| Bereich | Status |\n| secrets_management | implemented |\n",
    )
    _write(
        root / "docs/production_10_10/no_go_rules.md",
        "No-Go: Secret Rotation evidence is required.\n",
    )
    _write(
        root / "docs/SECRETS_MATRIX.md",
        "Secrets use a secret-store / Vault and rotation policy.\n",
    )


def test_valid_lifecycle_fixture_passes(tmp_path: Path) -> None:
    _valid_fixture(tmp_path)
    summary = build_summary(run_checks(tmp_path))
    assert summary["ok"] is True


def test_missing_required_doc_fails(tmp_path: Path) -> None:
    _valid_fixture(tmp_path)
    (tmp_path / "docs/production_10_10/secrets_rotation_report_template.md").unlink()
    summary = build_summary(run_checks(tmp_path))
    assert summary["ok"] is False
    assert any(f["id"] == "report_template" for f in summary["failures"])


def test_missing_evidence_matrix_reference_fails(tmp_path: Path) -> None:
    _valid_fixture(tmp_path)
    _write(tmp_path / "docs/production_10_10/evidence_matrix.md", "no relevant row\n")
    summary = build_summary(run_checks(tmp_path))
    assert summary["ok"] is False
    assert any(
        f["id"] == "evidence_matrix_secrets_management"
        for f in summary["failures"]
    )


def test_no_go_rules_must_mention_secret_rotation(tmp_path: Path) -> None:
    _valid_fixture(tmp_path)
    _write(tmp_path / "docs/production_10_10/no_go_rules.md", "No-Go only.\n")
    summary = build_summary(run_checks(tmp_path))
    assert any(f["id"] == "no_go_secret_rotation" for f in summary["failures"])


def test_rotation_docs_with_raw_secret_pattern_fail(tmp_path: Path) -> None:
    _valid_fixture(tmp_path)
    raw = "value=" + "sk-live-" + ("a" * 24)
    _write(
        tmp_path
        / "docs/production_10_10/secrets_rotation_and_credential_hygiene.md",
        raw,
    )
    summary = build_summary(run_checks(tmp_path))
    assert any(
        f["id"].startswith("no_raw_secret_pattern:")
        for f in summary["failures"]
    )


def test_json_output_is_parseable() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "ok" in payload
    assert "checks" in payload
