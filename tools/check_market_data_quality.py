#!/usr/bin/env python3
"""Validiert den Asset-Market-Data-Quality-Report fail-closed."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "asset_data_quality.json"
REQUIRED_FIELDS = (
    "asset",
    "market_family",
    "status",
    "live_allowed",
    "paper_allowed",
    "shadow_allowed",
    "reasons",
    "freshness",
    "gaps",
    "plausibility",
    "cross_source",
    "checked_at",
    "evidence_level",
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


def _load_report(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def analyze_market_data_quality(*, report_path: Path = DEFAULT_REPORT, strict_live: bool = False) -> dict[str, Any]:
    issues: list[CheckerIssue] = []
    report = _load_report(report_path)
    if report is None:
        _issue(
            issues,
            severity="error",
            code="report_missing_or_invalid",
            message="Market-Data-Report fehlt oder ist kein gueltiges JSON.",
            path=report_path,
        )
    else:
        for field in REQUIRED_FIELDS:
            if field not in report:
                _issue(
                    issues,
                    severity="error",
                    code="missing_required_field",
                    message=f"Pflichtfeld fehlt im Report: {field}",
                    path=report_path,
                )
        status = str(report.get("status") or "").lower()
        evidence_level = str(report.get("evidence_level") or "").lower()
        live_allowed = bool(report.get("live_allowed"))
        if status in {"fail", "warn", "not_enough_evidence"} and live_allowed:
            _issue(
                issues,
                severity="error",
                code="live_allowed_with_bad_status",
                message="Live ist erlaubt, obwohl Datenqualitaet nicht pass ist.",
                path=report_path,
            )
        if evidence_level != "runtime":
            _issue(
                issues,
                severity="warning",
                code="runtime_evidence_missing",
                message="Runtime-Evidence fehlt oder ist nicht als runtime markiert.",
                path=report_path,
            )
        if strict_live:
            if status != "pass":
                _issue(
                    issues,
                    severity="error",
                    code="strict_live_status_not_pass",
                    message=f"--strict-live blockiert: status={status!r} ist nicht pass.",
                    path=report_path,
                )
            if evidence_level != "runtime":
                _issue(
                    issues,
                    severity="error",
                    code="strict_live_runtime_required",
                    message="--strict-live blockiert: evidence_level ist nicht runtime.",
                    path=report_path,
                )
            if not live_allowed:
                _issue(
                    issues,
                    severity="error",
                    code="strict_live_live_not_allowed",
                    message="--strict-live blockiert: live_allowed ist false.",
                    path=report_path,
                )

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "report_path": str(report_path),
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_market_data_quality: report validation",
        f"ok={str(summary['ok']).lower()} report_path={summary['report_path']}",
    ]
    for issue in summary["issues"]:
        where = f" [{issue['path']}]" if issue.get("path") else ""
        lines.append(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{where}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--strict-live", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    summary = analyze_market_data_quality(report_path=args.report, strict_live=args.strict_live)
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
