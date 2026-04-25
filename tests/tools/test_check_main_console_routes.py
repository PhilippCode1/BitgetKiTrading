from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.check_main_console_routes import analyze_routes


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_main_console_routes.py"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mk_app(tmp_path: Path) -> Path:
    app = tmp_path / "apps" / "dashboard" / "src" / "app"
    _write(app / "(operator)" / "console" / "page.tsx", "export default function Page(){return null}\n")
    _write(app / "(operator)" / "console" / "ops" / "page.tsx", "export default function Page(){return null}\n")
    _write(app / "api" / "dashboard" / "edge-status" / "route.ts", "export async function GET(){return Response.json({ok:true})}\n")
    return app


def _mk_ia(tmp_path: Path, *, include_labels: bool = True) -> Path:
    doc = tmp_path / "docs" / "production_10_10" / "main_console_information_architecture.md"
    labels = "\n".join(
        [
            "- Übersicht -> `/console`",
            "- Bitget Assets -> `/console/market-universe`",
            "- Signale & Strategien -> `/console/signals`",
            "- Risk & Portfolio -> `/console/ops`",
            "- Live-Broker -> `/console/live-broker`",
            "- Shadow & Evidence -> `/console/shadow-live`",
            "- System Health -> `/console/health`",
            "- Einstellungen -> `/console/account/language`",
            "- Reports -> `/console/usage`",
            "- Admin/Owner -> `/console/admin`",
        ]
    )
    if not include_labels:
        labels = "- Navigation fehlt.\n"
    _write(
        doc,
        "\n".join(
            [
                "# Main Console IA",
                "## Zentrale Navigation",
                labels,
                "## Routen-Mapping",
                "- `/console`",
                "- `/console/ops`",
                "- `/api/dashboard/edge-status`",
                "## Konsolidierungsregeln",
                "- Legacy-Routen zuerst inventarisieren.",
            ]
        )
        + "\n",
    )
    return doc


def test_tool_detects_routes(tmp_path: Path) -> None:
    app = _mk_app(tmp_path)
    ia = _mk_ia(tmp_path)
    summary = analyze_routes(app, ia)
    assert summary["ui_route_count"] >= 2
    assert summary["api_route_count"] >= 1


def test_tool_detects_missing_main_console_doc(tmp_path: Path) -> None:
    app = _mk_app(tmp_path)
    missing_doc = tmp_path / "docs" / "production_10_10" / "main_console_information_architecture.md"
    summary = analyze_routes(app, missing_doc)
    codes = {issue["code"] for issue in summary["issues"]}
    assert "ia_doc_missing" in codes


def test_tool_detects_irrelevant_billing_customer_terms(tmp_path: Path) -> None:
    app = _mk_app(tmp_path)
    _write(app / "(customer)" / "portal" / "billing" / "page.tsx", "export default function Page(){return null}\n")
    ia = _mk_ia(tmp_path)
    summary = analyze_routes(app, ia)
    codes = [issue["code"] for issue in summary["issues"]]
    assert "irrelevant_term_detected" in codes


def test_tool_detects_missing_german_navigation(tmp_path: Path) -> None:
    app = _mk_app(tmp_path)
    ia = _mk_ia(tmp_path, include_labels=False)
    summary = analyze_routes(app, ia)
    codes = {issue["code"] for issue in summary["issues"]}
    assert "ia_missing_german_navigation" in codes


def test_json_output_is_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert "ui_route_count" in payload
    assert "issues" in payload


def test_strict_fails_when_central_structure_missing(tmp_path: Path) -> None:
    app = _mk_app(tmp_path)
    ia = tmp_path / "docs" / "production_10_10" / "main_console_information_architecture.md"
    _write(
        ia,
        "# IA\n\n## Zentrale Navigation\n- `/console`\n",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--strict",
            "--app-dir",
            str(app),
            "--ia-doc",
            str(ia),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "ia_missing_section" in completed.stdout
