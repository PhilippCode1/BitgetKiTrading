#!/usr/bin/env python3
"""Static checks for private audit, forensics and replay deliverables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "audit_forensics_replay_private_console.md"
CONTRACT_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "audit_contracts.py"
REPLAY_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "replay_summary.py"
MAIN_CONSOLE_DOC = ROOT / "docs" / "dashboard_operator_console.md"
TEST_PATHS = (
    ROOT / "tests" / "security" / "test_private_audit_forensics_contracts.py",
    ROOT / "tests" / "tools" / "test_check_private_audit_forensics.py",
)


@dataclass(frozen=True)
class AuditCheckerIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _issue(
    issues: list[AuditCheckerIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: Path | None = None,
) -> None:
    issues.append(
        AuditCheckerIssue(
            severity=severity,
            code=code,
            message=message,
            path=str(path) if path else None,
        )
    )


def analyze_private_audit_forensics() -> dict[str, Any]:
    issues: list[AuditCheckerIssue] = []

    if not DOC_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="doc_missing",
            message="Audit/Forensics/Replay production document missing.",
            path=DOC_PATH,
        )
        doc_text = ""
    else:
        doc_text = DOC_PATH.read_text(encoding="utf-8").lower()

    for path, code in (
        (CONTRACT_PATH, "audit_contract_missing"),
        (REPLAY_PATH, "replay_summary_missing"),
    ):
        if not path.is_file():
            _issue(
                issues,
                severity="error",
                code=code,
                message=f"Required shared module missing: {path.name}",
                path=path,
            )

    for path in TEST_PATHS:
        if not path.is_file():
            _issue(
                issues,
                severity="error",
                code="test_missing",
                message="Required private audit forensics test missing.",
                path=path,
            )

    if not MAIN_CONSOLE_DOC.is_file():
        _issue(
            issues,
            severity="error",
            code="main_console_doc_missing",
            message="Main Console documentation missing.",
            path=MAIN_CONSOLE_DOC,
        )
        main_console_text = ""
    else:
        main_console_text = MAIN_CONSOLE_DOC.read_text(encoding="utf-8").lower()

    combined = f"{doc_text}\n{main_console_text}"
    for required in (
        "letzte blockierte live-entscheidungen",
        "do_not_trade",
        "asset-quarantaene",
        "reconcile-drifts",
        "safety-latch",
        "bitget-readiness",
        "deutsche zusammenfassung",
    ):
        if required not in combined:
            _issue(
                issues,
                severity="error",
                code="forensics_main_console_hint_missing",
                message=f"Missing Main Console forensics hint: {required}",
                path=DOC_PATH,
            )

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": not errors,
        "doc_exists": DOC_PATH.is_file(),
        "contract_exists": CONTRACT_PATH.is_file(),
        "replay_summary_exists": REPLAY_PATH.is_file(),
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_private_audit_forensics: private console audit surface",
        f"ok={str(summary['ok']).lower()} doc_exists={summary['doc_exists']} contract_exists={summary['contract_exists']} replay_summary_exists={summary['replay_summary_exists']}",
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

    summary = analyze_private_audit_forensics()
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
