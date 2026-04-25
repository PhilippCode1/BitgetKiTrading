from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

from tools.check_10_10_evidence import (
    FORBIDDEN_REQUIRED_CATEGORY_IDS,
    REQUIRED_CATEGORY_IDS,
    load_matrix,
    validate_matrix,
)


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_10_10_evidence.py"


def _category(category_id: str, evidence_file: Path, **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": category_id,
        "title": category_id.replace("_", " ").title(),
        "description": "Test category.",
        "target_10_10": "Test target.",
        "required_evidence": ["Test evidence."],
        "evidence_files": [str(evidence_file)],
        "required_commands": ["python tools/check_10_10_evidence.py"],
        "status": "verified",
        "blocks_live_trading": False,
        "severity": "P2",
        "owner_role": "Test",
        "next_action": "None.",
        "notes": "Synthetic test matrix.",
    }
    data.update(overrides)
    return data


def _write_matrix(tmp_path: Path, categories: list[dict[str, object]]) -> Path:
    path = tmp_path / "matrix.yaml"
    path.write_text(yaml.safe_dump({"categories": categories}, sort_keys=False), encoding="utf-8")
    return path


def _valid_categories(tmp_path: Path) -> list[dict[str, object]]:
    evidence_file = tmp_path / "evidence.md"
    evidence_file.write_text("ok\n", encoding="utf-8")
    return [_category(category_id, evidence_file) for category_id in REQUIRED_CATEGORY_IDS]


def test_repository_matrix_is_valid() -> None:
    data = load_matrix(ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml")
    issues = validate_matrix(data, root=ROOT)
    assert not [issue for issue in issues if issue.severity == "error"]


def test_missing_required_field_creates_error(tmp_path: Path) -> None:
    categories = _valid_categories(tmp_path)
    categories[0].pop("title")
    issues = validate_matrix({"categories": categories}, root=ROOT)
    assert any(issue.code == "missing_required_field" for issue in issues)


def test_unknown_status_creates_error(tmp_path: Path) -> None:
    categories = _valid_categories(tmp_path)
    categories[0]["status"] = "done"
    issues = validate_matrix({"categories": categories}, root=ROOT)
    assert any(issue.code == "unknown_status" for issue in issues)


def test_strict_fails_for_not_verified_live_blocker(tmp_path: Path) -> None:
    categories = _valid_categories(tmp_path)
    categories[0]["blocks_live_trading"] = True
    categories[0]["status"] = "partial"
    matrix = _write_matrix(tmp_path, categories)
    result = subprocess.run(
        [sys.executable, str(TOOL), "--matrix", str(matrix), "--strict"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "live_blocker_not_verified" in result.stdout


def test_json_output_is_parseable() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["category_count"] == len(REQUIRED_CATEGORY_IDS)
    assert "live_blockers" in parsed


def test_report_is_created(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    result = subprocess.run(
        [sys.executable, str(TOOL), "--write-report", str(report)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.returncode == 0
    content = report.read_text(encoding="utf-8")
    assert "# Evidence Status Report" in content
    assert "Live-Blocker" in content


def test_verified_with_missing_evidence_file_fails_strict(tmp_path: Path) -> None:
    categories = _valid_categories(tmp_path)
    categories[0]["evidence_files"] = [str(tmp_path / "missing.md")]
    matrix = _write_matrix(tmp_path, categories)
    result = subprocess.run(
        [sys.executable, str(TOOL), "--matrix", str(matrix), "--strict"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "missing_evidence_file" in result.stdout


def test_billing_customer_sales_categories_are_not_required() -> None:
    assert "billing_commercial_gates" not in REQUIRED_CATEGORY_IDS
    assert "customer_ui" not in REQUIRED_CATEGORY_IDS
    assert "tenant_isolation" not in REQUIRED_CATEGORY_IDS
    assert {"billing_commercial_gates", "customer_ui", "tenant_isolation"}.issubset(
        FORBIDDEN_REQUIRED_CATEGORY_IDS
    )


def test_german_only_ui_is_required_category() -> None:
    assert "german_only_ui" in REQUIRED_CATEGORY_IDS


def test_main_console_information_architecture_is_required_category() -> None:
    assert "main_console_information_architecture" in REQUIRED_CATEGORY_IDS
