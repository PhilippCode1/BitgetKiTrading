#!/usr/bin/env python3
"""Static checks fuer Liquidity/Spread/Slippage deliverables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "liquidity_spread_slippage_per_asset.md"
MODULE_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "liquidity_scoring.py"
SCRIPT_PATH = ROOT / "scripts" / "liquidity_quality_report.py"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "liquidity_quality_sample.json"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
TEST_PATHS = (
    ROOT / "tests" / "risk" / "test_liquidity_scoring.py",
    ROOT / "tests" / "security" / "test_liquidity_live_blocking.py",
    ROOT / "tests" / "scripts" / "test_liquidity_quality_report.py",
    ROOT / "tests" / "tools" / "test_check_liquidity_quality.py",
)


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
    for path, code, message in (
        (DOC_PATH, "doc_missing", "Dokumentation fehlt."),
        (MODULE_PATH, "module_missing", "liquidity_scoring.py fehlt."),
        (SCRIPT_PATH, "script_missing", "liquidity_quality_report.py fehlt."),
        (FIXTURE_PATH, "fixture_missing", "liquidity_quality_sample.json fehlt."),
    ):
        if not path.is_file():
            _issue(issues, severity="error", code=code, message=message, path=path)
    for path in TEST_PATHS:
        if not path.is_file():
            _issue(issues, severity="error", code="test_missing", message="Erforderlicher Test fehlt.", path=path)

    if MAIN_CONSOLE_DOC_PATH.is_file():
        text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        required_terms = ("spread", "slippage", "liquidit")
        if not all(term in text for term in required_terms):
            _issue(
                issues,
                severity="error",
                code="main_console_liquidity_missing",
                message="Main-Console-Doku erwaehnt Liquiditaetsmodul nicht ausreichend.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="main_console_doc_missing", message="Main-Console-Doku fehlt.", path=MAIN_CONSOLE_DOC_PATH)

    if NO_GO_DOC_PATH.is_file():
        text = NO_GO_DOC_PATH.read_text(encoding="utf-8").lower()
        if not ("liquiditaet" in text and "stale" in text):
            _issue(
                issues,
                severity="error",
                code="no_go_liquidity_reference_missing",
                message="No-Go-Regeln erwaehnen schlechte/stale Liquiditaet nicht klar.",
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
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    summary = analyze()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"check_liquidity_quality: ok={str(summary['ok']).lower()} "
            f"errors={summary['error_count']} warnings={summary['warning_count']}"
        )
        for issue in summary["issues"]:
            where = f" [{issue['path']}]" if issue.get("path") else ""
            print(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{where}")

    if summary["error_count"] > 0:
        return 1
    if args.strict and summary["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
