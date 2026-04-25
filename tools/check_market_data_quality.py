#!/usr/bin/env python3
"""Static checks for market data quality and quarantine deliverables."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "market_data_quality_per_asset.md"
SCRIPT_PATH = ROOT / "scripts" / "market_data_quality_report.py"
MATRIX_PATH = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "market_data_quality_sample.json"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
TEST_PATHS = (
    ROOT / "tests" / "scripts" / "test_market_data_quality_report.py",
    ROOT / "tests" / "tools" / "test_check_market_data_quality.py",
    ROOT / "tests" / "security" / "test_market_data_quality_live_blocking.py",
    ROOT / "tests" / "data" / "test_market_data_quality.py",
)

UNSAFE_LIVE_PHRASES = (
    "livefähig ohne datenqualität",
    "livefaehig ohne datenqualitaet",
    "live ohne datenprüfung",
    "live ohne datenpruefung",
    "alle assets live ohne qualitätsgate",
    "all assets live without data quality",
)


@dataclass(frozen=True)
class CheckerIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _issue(
    issues: list[CheckerIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    issues.append(
        CheckerIssue(
            severity=severity,
            code=code,
            message=message,
            path=str(path) if path else None,
        )
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def analyze_market_data_quality() -> dict[str, Any]:
    issues: list[CheckerIssue] = []

    if not DOC_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="doc_missing",
            message="Missing market_data_quality_per_asset.md documentation.",
            path=DOC_PATH,
        )
        doc_text = ""
    else:
        doc_text = DOC_PATH.read_text(encoding="utf-8").lower()

    if not SCRIPT_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="script_missing",
            message="Missing scripts/asset_data_quality_report.py.",
            path=SCRIPT_PATH,
        )
    if not FIXTURE_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="fixture_missing",
            message="Missing tests/fixtures/market_data_quality_sample.json.",
            path=FIXTURE_PATH,
        )

    for test_path in TEST_PATHS:
        if not test_path.is_file():
            _issue(
                issues,
                severity="error",
                code="test_missing",
                message="Required market-data-quality test missing.",
                path=test_path,
            )

    matrix_has_category = False
    if MATRIX_PATH.is_file():
        matrix = _load_yaml(MATRIX_PATH)
        categories = matrix.get("categories")
        if isinstance(categories, list):
            matrix_has_category = any(
                isinstance(item, dict) and str(item.get("id")) == "market_data_quality_per_asset"
                for item in categories
            )
    if not matrix_has_category:
        _issue(
            issues,
            severity="warning",
            code="matrix_reference_missing",
            message="Evidence matrix does not reference market_data_quality_per_asset.",
            path=MATRIX_PATH,
        )

    for phrase in UNSAFE_LIVE_PHRASES:
        if phrase in doc_text:
            negated = re.search(rf"(nicht|kein)\s+[^.\n]{{0,24}}{re.escape(phrase)}", doc_text)
            if negated:
                continue
            _issue(
                issues,
                severity="error",
                code="unsafe_live_claim",
                message=f"Unsafe live claim in documentation: {phrase}",
                path=DOC_PATH,
            )
    if MAIN_CONSOLE_DOC_PATH.is_file():
        main_console_text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        if "datenqualitaet" not in main_console_text:
            _issue(
                issues,
                severity="error",
                code="main_console_data_quality_missing",
                message="Main-Console-Doku erwaehnt Datenqualitaet-Modul nicht.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="main_console_doc_missing",
            message="Missing main_console_product_direction.md.",
            path=MAIN_CONSOLE_DOC_PATH,
        )
    if NO_GO_DOC_PATH.is_file():
        no_go_text = NO_GO_DOC_PATH.read_text(encoding="utf-8").lower()
        has_data_quality = "datenqualitaet" in no_go_text
        has_stale_reference = ("stale" in no_go_text) or ("data_stale" in no_go_text)
        if not (has_data_quality and has_stale_reference):
            _issue(
                issues,
                severity="error",
                code="no_go_data_quality_reference_missing",
                message="No-Go-Regeln erwaehnen schlechte/stale Datenqualitaet nicht klar genug.",
                path=NO_GO_DOC_PATH,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="no_go_doc_missing",
            message="Missing no_go_rules.md.",
            path=NO_GO_DOC_PATH,
        )

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "doc_exists": DOC_PATH.is_file(),
        "script_exists": SCRIPT_PATH.is_file(),
        "fixture_exists": FIXTURE_PATH.is_file(),
        "matrix_has_market_data_quality_per_asset": matrix_has_category,
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_market_data_quality: evidence surface",
        f"ok={str(summary['ok']).lower()} doc_exists={summary['doc_exists']} script_exists={summary['script_exists']}",
        "matrix_has_market_data_quality_per_asset="
        + str(summary["matrix_has_market_data_quality_per_asset"]).lower(),
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

    summary = analyze_market_data_quality()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_text(summary))

    if summary["error_count"] > 0:
        return 1
    if args.strict and summary["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
