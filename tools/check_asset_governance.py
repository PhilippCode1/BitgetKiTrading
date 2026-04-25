#!/usr/bin/env python3
"""Static checks fuer Asset Governance Deliverables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "asset_quarantine_and_live_allowlist.md"
MODULE_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "asset_governance.py"
SCRIPT_PATH = ROOT / "scripts" / "asset_governance_report.py"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
TEST_PATHS = (
    ROOT / "tests" / "shared" / "test_asset_governance.py",
    ROOT / "tests" / "scripts" / "test_asset_governance_report.py",
    ROOT / "tests" / "tools" / "test_check_asset_governance.py",
)
REQUIRED_MAIN_CONSOLE_TERM = "asset-freigaben"
NO_GO_PRIMARY_TERM = "asset-freigabe"
NO_GO_SECONDARY_TERMS = ("kein live", "kein echtgeld-live", "block")


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _issue(
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    issues.append(Issue(severity=severity, code=code, message=message, path=str(path) if path else None))


def analyze() -> dict[str, Any]:
    issues: list[Issue] = []
    if not DOC_PATH.is_file():
        _issue(issues, severity="error", code="doc_missing", message="Dokumentation fehlt.", path=DOC_PATH)
    if not MODULE_PATH.is_file():
        _issue(issues, severity="error", code="module_missing", message="Governance-Modul fehlt.", path=MODULE_PATH)
    if not SCRIPT_PATH.is_file():
        _issue(issues, severity="error", code="script_missing", message="Report-Script fehlt.", path=SCRIPT_PATH)
    for path in TEST_PATHS:
        if not path.is_file():
            _issue(issues, severity="error", code="test_missing", message="Erforderlicher Test fehlt.", path=path)
    if MAIN_CONSOLE_DOC_PATH.is_file():
        text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        if REQUIRED_MAIN_CONSOLE_TERM not in text:
            _issue(
                issues,
                severity="error",
                code="main_console_term_missing",
                message="Main-Console-Doku erwaehnt Asset-Freigaben nicht.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="main_console_doc_missing", message="Main-Console-Doku fehlt.", path=MAIN_CONSOLE_DOC_PATH)
    if NO_GO_DOC_PATH.is_file():
        text = NO_GO_DOC_PATH.read_text(encoding="utf-8").lower()
        has_primary = NO_GO_PRIMARY_TERM in text
        has_secondary = any(term in text for term in NO_GO_SECONDARY_TERMS)
        if not (has_primary and has_secondary):
            _issue(
                issues,
                severity="error",
                code="no_go_terms_missing",
                message="No-Go-Regeln blockieren unfreigegebene Assets nicht klar genug.",
                path=NO_GO_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="no_go_doc_missing", message="No-Go-Doku fehlt.", path=NO_GO_DOC_PATH)

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
        "doc_exists": DOC_PATH.is_file(),
        "module_exists": MODULE_PATH.is_file(),
        "script_exists": SCRIPT_PATH.is_file(),
    }


def render(summary: dict[str, Any]) -> str:
    lines = [
        "check_asset_governance: deliverables",
        f"ok={str(summary['ok']).lower()} doc_exists={summary['doc_exists']} module_exists={summary['module_exists']} script_exists={summary['script_exists']}",
    ]
    for issue in summary["issues"]:
        where = f" [{issue['path']}]" if issue.get("path") else ""
        lines.append(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{where}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = analyze()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render(summary))

    if summary["error_count"] > 0:
        return 1
    if args.strict and summary["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
