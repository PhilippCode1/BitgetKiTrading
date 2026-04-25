#!/usr/bin/env python3
"""Check Main Console BFF/API wiring evidence."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = Path("docs/production_10_10/main_console_bff_api_wiring.md")
EVIDENCE_PATH = Path("docs/production_10_10/evidence_matrix.yaml")
DASHBOARD_API_PATH = Path("apps/dashboard/src/app/api")
DASHBOARD_APP_PATH = Path("apps/dashboard/src/app")

STATUS_ERROR = "error"
STATUS_WARNING = "warning"

REQUIRED_AREAS: tuple[tuple[str, str], ...] = (
    ("systemzustand", "Systemzustand"),
    ("bitget-readiness", "Bitget Readiness"),
    ("asset-universe", "Asset Universe"),
    ("asset-live-eligibility", "Asset Live Eligibility"),
    ("market-data-quality", "Market Data Quality"),
    ("signals", "Signals"),
    ("ki-erklaerung", "KI-Erklärung"),
    ("risk-governor", "Risk Governor"),
    ("portfolio-risk", "Portfolio Risk"),
    ("live-broker", "Live-Broker"),
    ("reconcile", "Reconcile"),
    ("kill-switch", "Kill-Switch"),
    ("safety-latch", "Safety-Latch"),
    ("shadow-burn-in", "Shadow Burn-in"),
    ("restore-safety-evidence", "Restore/Safety Evidence"),
    ("alerts", "Alerts"),
    ("reports", "Reports"),
    ("settings", "Settings"),
)

REQUIRED_STATUS_TERMS = ("loading", "ready", "empty", "degraded", "error", "unavailable")
REQUIRED_COLUMN_TERMS = (
    "ui-komponente",
    "bff-route",
    "gateway/api-route",
    "service-quelle",
    "datenmodus",
    "ladezustand",
    "fehlerzustand",
    "empty state",
    "live-relevanz",
    "deutscher ui-text",
)


@dataclass(frozen=True)
class WiringIssue:
    severity: str
    code: str
    message: str


def _issue(issues: list[WiringIssue], severity: str, code: str, message: str) -> None:
    issues.append(WiringIssue(severity=severity, code=code, message=message))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _norm(text: str) -> str:
    return text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


def validate_wiring(root: Path = ROOT, *, strict: bool = False) -> list[WiringIssue]:
    issues: list[WiringIssue] = []
    doc = root / DOC_PATH
    api_dir = root / DASHBOARD_API_PATH
    app_dir = root / DASHBOARD_APP_PATH
    evidence = root / EVIDENCE_PATH

    if not doc.is_file():
        _issue(issues, STATUS_ERROR, "doc_missing", f"missing {DOC_PATH.as_posix()}")
        return issues
    if not api_dir.is_dir():
        _issue(issues, STATUS_ERROR, "dashboard_api_missing", f"missing {DASHBOARD_API_PATH.as_posix()}")
    if not app_dir.is_dir():
        _issue(issues, STATUS_ERROR, "dashboard_app_missing", f"missing {DASHBOARD_APP_PATH.as_posix()}")
    if not evidence.is_file():
        _issue(issues, STATUS_ERROR, "evidence_matrix_missing", f"missing {EVIDENCE_PATH.as_posix()}")

    text = _read_text(doc)
    normalized = _norm(text)

    for slug, label in REQUIRED_AREAS:
        if slug not in normalized and _norm(label) not in normalized:
            _issue(issues, STATUS_ERROR, "required_area_missing", f"missing required area: {label}")

    for term in REQUIRED_STATUS_TERMS:
        if term not in normalized:
            _issue(issues, STATUS_ERROR, "status_model_term_missing", f"missing status model term: {term}")

    for term in REQUIRED_COLUMN_TERMS:
        if term not in normalized:
            _issue(issues, STATUS_ERROR, "wiring_column_missing", f"missing wiring field: {term}")

    if "fehlermeld" not in normalized and "fehlerzustand" not in normalized:
        _issue(issues, STATUS_ERROR, "error_state_doc_missing", "German error-state documentation missing")
    if "empty state" not in normalized:
        _issue(issues, STATUS_ERROR, "empty_state_doc_missing", "empty-state documentation missing")
    if "loading" not in normalized and "ladezustand" not in normalized:
        _issue(issues, STATUS_ERROR, "loading_state_doc_missing", "loading-state documentation missing")
    if "/api/dashboard/" not in normalized:
        _issue(issues, STATUS_ERROR, "bff_doc_missing", "BFF routes under /api/dashboard are not documented")
    if "keine secrets im browser" not in normalized and "keine secrets" not in normalized:
        _issue(issues, STATUS_ERROR, "browser_secret_rule_missing", "browser secret rule missing")

    if re.search(r"pflicht(?:bereich|karte|route|secret|variable)?[^\n]{0,80}(billing|customer|payment|checkout)", normalized):
        _issue(
            issues,
            STATUS_ERROR,
            "billing_customer_required",
            "Billing/Customer/Payment flow appears as a required Main Console dependency",
        )

    if evidence.is_file():
        evidence_text = _read_text(evidence)
        evidence_norm = _norm(evidence_text)
        required_refs = (
            "main_console_bff_api_wiring.md",
            "check_main_console_wiring.py",
            "test_check_main_console_wiring.py",
        )
        for ref in required_refs:
            if ref not in evidence_norm:
                _issue(issues, STATUS_ERROR, "evidence_reference_missing", f"evidence matrix missing {ref}")

    if strict:
        route_count = len(list(api_dir.rglob("route.ts"))) if api_dir.is_dir() else 0
        if route_count < 1:
            _issue(issues, STATUS_ERROR, "dashboard_api_routes_missing", "no dashboard API route.ts files found")
    return issues


def build_summary(issues: list[WiringIssue], *, strict: bool) -> dict[str, Any]:
    errors = [issue for issue in issues if issue.severity == STATUS_ERROR]
    warnings = [issue for issue in issues if issue.severity == STATUS_WARNING]
    return {
        "ok": not errors,
        "strict": strict,
        "required_area_count": len(REQUIRED_AREAS),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(issue) for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    issues = validate_wiring(args.root, strict=args.strict)
    summary = build_summary(issues, strict=args.strict)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        mode = "strict" if args.strict else "default"
        print(f"main_console_wiring: mode={mode}")
        print(
            f"ok={str(summary['ok']).lower()} errors={summary['error_count']} "
            f"warnings={summary['warning_count']} areas={summary['required_area_count']}"
        )
        for issue in issues:
            print(f"{issue.severity.upper()} {issue.code}: {issue.message}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
