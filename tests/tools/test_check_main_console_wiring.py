from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_main_console_wiring import REQUIRED_AREAS, validate_wiring


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_main_console_wiring.py"


def _write_minimal_repo(tmp_path: Path, doc_text: str) -> None:
    doc = tmp_path / "docs" / "production_10_10" / "main_console_bff_api_wiring.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(doc_text, encoding="utf-8")
    evidence = tmp_path / "docs" / "production_10_10" / "evidence_matrix.yaml"
    evidence.write_text(
        "\n".join(
            [
                "evidence_files:",
                "  - docs/production_10_10/main_console_bff_api_wiring.md",
                "  - tools/check_main_console_wiring.py",
                "  - tests/tools/test_check_main_console_wiring.py",
            ]
        ),
        encoding="utf-8",
    )
    api = tmp_path / "apps" / "dashboard" / "src" / "app" / "api" / "dashboard"
    api.mkdir(parents=True)
    (api / "route.ts").write_text("export async function GET() {}", encoding="utf-8")


def _valid_doc() -> str:
    area_lines = "\n".join(f"- {slug}: {label}" for slug, label in REQUIRED_AREAS)
    return f"""
# Main Console BFF/API Wiring

Statusmodell: loading, ready, empty, degraded, error, unavailable.

Felder: UI-Komponente, BFF-Route, Gateway/API-Route, Service-Quelle,
Datenmodus, Ladezustand, Fehlerzustand, Empty State, Live-Relevanz, deutscher UI-Text.

Die BFF-Route nutzt /api/dashboard/gateway/v1/system/health.
Keine Secrets im Browser. Billing, Customer und Payment sind out-of-scope.
Deutsche Fehlermeldungen sind Pflicht fuer Fehlerzustand.

{area_lines}
"""


def _codes(root: Path, *, strict: bool = False) -> set[str]:
    return {issue.code for issue in validate_wiring(root, strict=strict)}


def test_checker_detects_missing_required_area(tmp_path: Path) -> None:
    doc = _valid_doc().replace("asset-universe: Asset Universe", "")
    _write_minimal_repo(tmp_path, doc)
    assert "required_area_missing" in _codes(tmp_path)


def test_checker_detects_missing_error_state_doc(tmp_path: Path) -> None:
    doc = _valid_doc().replace("Fehlerzustand", "").replace("Fehlermeldungen", "")
    _write_minimal_repo(tmp_path, doc)
    assert "error_state_doc_missing" in _codes(tmp_path)


def test_checker_detects_missing_bff_doc(tmp_path: Path) -> None:
    doc = _valid_doc().replace("/api/dashboard/gateway/v1/system/health", "/v1/system/health")
    _write_minimal_repo(tmp_path, doc)
    assert "bff_doc_missing" in _codes(tmp_path)


def test_json_output_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(completed.stdout)
    assert parsed["required_area_count"] == len(REQUIRED_AREAS)
    assert parsed["ok"] is True


def test_strict_fails_correctly_without_dashboard_api(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path, _valid_doc())
    api_dir = tmp_path / "apps" / "dashboard" / "src" / "app" / "api" / "dashboard"
    for file in api_dir.glob("*.ts"):
        file.unlink()
    assert "dashboard_api_routes_missing" in _codes(tmp_path, strict=True)
