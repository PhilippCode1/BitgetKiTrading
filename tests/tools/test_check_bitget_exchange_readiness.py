from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_bitget_exchange_readiness import validate


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_bitget_exchange_readiness.py"


def _write_minimal_repo(tmp_path: Path, doc_text: str) -> None:
    doc = tmp_path / "docs" / "production_10_10" / "bitget_exchange_readiness.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(doc_text, encoding="utf-8")
    no_go = tmp_path / "docs" / "production_10_10" / "no_go_rules.md"
    no_go.write_text("Bitget Readiness Withdrawal API-Version", encoding="utf-8")
    evidence = tmp_path / "docs" / "production_10_10" / "evidence_matrix.yaml"
    evidence.write_text(
        "\n".join(
            [
                "docs/production_10_10/bitget_exchange_readiness.md",
                "scripts/bitget_readiness_check.py",
                "tools/check_bitget_exchange_readiness.py",
                "tests/scripts/test_bitget_readiness_check.py",
                "tests/security/test_bitget_exchange_readiness_contracts.py",
                "tests/tools/test_check_bitget_exchange_readiness.py",
            ]
        ),
        encoding="utf-8",
    )
    for rel in (
        "scripts/bitget_readiness_check.py",
        "tools/check_bitget_exchange_readiness.py",
        "tests/scripts/test_bitget_readiness_check.py",
        "tests/security/test_bitget_exchange_readiness_contracts.py",
        "tests/tools/test_check_bitget_exchange_readiness.py",
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("dry-run readonly demo-safe live_write_allowed", encoding="utf-8")


def _valid_doc() -> str:
    return """
# Bitget Exchange Readiness
Zielbild Read-only Write Demo Live API-Version Permissions Withdrawal
Server-Time Rate-Limit Instrument Discovery Live-Gates No-Go Tests.
Keine echten Secrets.
"""


def _codes(root: Path, *, strict: bool = False) -> set[str]:
    return {issue.code for issue in validate(root, strict=strict)}


def test_checker_detects_missing_doc(tmp_path: Path) -> None:
    assert "required_file_missing" in _codes(tmp_path)


def test_checker_detects_missing_required_doc_term(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path, _valid_doc().replace("Withdrawal", ""))
    assert "doc_term_missing" in _codes(tmp_path)


def test_checker_detects_forbidden_script_write_call(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path, _valid_doc())
    (tmp_path / "scripts" / "bitget_readiness_check.py").write_text(
        "dry-run readonly demo-safe live_write_allowed\nclient.place_order({})",
        encoding="utf-8",
    )
    assert "script_write_call_forbidden" in _codes(tmp_path)


def test_json_output_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["error_count"] == 0


def test_strict_passes_repository_surface() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--strict"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
