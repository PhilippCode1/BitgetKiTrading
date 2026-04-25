#!/usr/bin/env python3
"""Validate the private-owner 10/10 evidence matrix for bitget-btc-ai."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"

ALLOWED_STATUSES = {
    "missing",
    "partial",
    "implemented",
    "verified",
    "external_required",
}
ALLOWED_SEVERITIES = {"P0", "P1", "P2", "P3"}

REQUIRED_FIELDS = (
    "id",
    "title",
    "description",
    "target_10_10",
    "required_evidence",
    "evidence_files",
    "required_commands",
    "status",
    "blocks_live_trading",
    "severity",
    "owner_role",
    "next_action",
    "notes",
)

REQUIRED_CATEGORY_IDS = (
    "private_owner_scope",
    "main_console_information_architecture",
    "german_only_ui",
    "bitget_asset_universe",
    "instrument_catalog",
    "asset_quarantine_and_delisting",
    "market_data_quality_per_asset",
    "liquidity_spread_slippage_per_asset",
    "asset_risk_tiers",
    "multi_asset_order_sizing",
    "portfolio_risk",
    "strategy_validation_per_asset_class",
    "live_broker_fail_closed",
    "order_idempotency",
    "reconcile_safety",
    "kill_switch_safety_latch",
    "emergency_flatten",
    "bitget_exchange_readiness",
    "env_secrets_profiles",
    "observability_slos",
    "alert_routing",
    "backup_restore",
    "shadow_burn_in",
    "disaster_recovery",
    "audit_forensics",
    "frontend_main_console_security",
    "admin_access_single_owner",
    "deployment_parity",
    "supply_chain_security",
    "final_go_no_go_scorecard",
)

FORBIDDEN_REQUIRED_CATEGORY_IDS = {
    "billing_commercial_gates",
    "customer_ui",
    "tenant_isolation",
    "payment_provider_checks",
    "customer_contract_checks",
}


@dataclass(frozen=True)
class EvidenceIssue:
    severity: str
    code: str
    category_id: str | None
    message: str


def load_matrix(path: Path = DEFAULT_MATRIX) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError("matrix root must be a mapping")
    return loaded


def _issue(
    issues: list[EvidenceIssue],
    code: str,
    message: str,
    *,
    category_id: str | None = None,
    severity: str = "error",
) -> None:
    issues.append(
        EvidenceIssue(
            severity=severity,
            code=code,
            category_id=category_id,
            message=message,
        )
    )


def _categories(data: dict[str, Any]) -> list[dict[str, Any]]:
    categories = data.get("categories")
    if not isinstance(categories, list):
        return []
    return [item for item in categories if isinstance(item, dict)]


def _evidence_path_missing(path_value: str, *, root: Path) -> bool:
    path = Path(path_value)
    if path.is_absolute():
        return not path.exists()
    return not (root / path).exists()


def validate_matrix(data: dict[str, Any], *, root: Path = ROOT) -> list[EvidenceIssue]:
    issues: list[EvidenceIssue] = []
    raw_categories = data.get("categories")
    if not isinstance(raw_categories, list):
        _issue(issues, "categories_missing", "categories must be a list")
        return issues

    categories = _categories(data)
    if len(categories) != len(raw_categories):
        _issue(issues, "category_not_mapping", "all categories must be mappings")

    seen: set[str] = set()
    for category in categories:
        category_id = str(category.get("id", "")).strip() or None
        for field in REQUIRED_FIELDS:
            if field not in category:
                _issue(
                    issues,
                    "missing_required_field",
                    f"missing required field: {field}",
                    category_id=category_id,
                )
        if not category_id:
            _issue(issues, "missing_category_id", "category id must be non-empty")
            continue
        if category_id in seen:
            _issue(
                issues,
                "duplicate_category_id",
                f"duplicate category id: {category_id}",
                category_id=category_id,
            )
        seen.add(category_id)

        status = category.get("status")
        if status not in ALLOWED_STATUSES:
            _issue(
                issues,
                "unknown_status",
                f"unknown status: {status!r}",
                category_id=category_id,
            )

        severity = category.get("severity")
        if severity not in ALLOWED_SEVERITIES:
            _issue(
                issues,
                "unknown_severity",
                f"unknown severity: {severity!r}",
                category_id=category_id,
            )

        if not isinstance(category.get("blocks_live_trading"), bool):
            _issue(
                issues,
                "invalid_blocks_live_trading",
                "blocks_live_trading must be a boolean",
                category_id=category_id,
            )

        for list_field in ("required_evidence", "evidence_files", "required_commands"):
            value = category.get(list_field)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                _issue(
                    issues,
                    "invalid_list_field",
                    f"{list_field} must be a list of strings",
                    category_id=category_id,
                )

        for text_field in (
            "title",
            "description",
            "target_10_10",
            "owner_role",
            "next_action",
            "notes",
        ):
            if text_field in category and not isinstance(category.get(text_field), str):
                _issue(
                    issues,
                    "invalid_text_field",
                    f"{text_field} must be a string",
                    category_id=category_id,
                )

        evidence_files = category.get("evidence_files")
        if isinstance(evidence_files, list):
            for evidence_file in evidence_files:
                if isinstance(evidence_file, str) and _evidence_path_missing(evidence_file, root=root):
                    _issue(
                        issues,
                        "missing_evidence_file",
                        f"missing evidence file: {evidence_file}",
                        category_id=category_id,
                        severity="warning",
                    )

        if (
            category.get("blocks_live_trading") is True
            and category.get("status") != "verified"
        ):
            _issue(
                issues,
                "live_blocker_not_verified",
                "blocks live trading and is not verified",
                category_id=category_id,
                severity="warning",
            )

    missing_required = sorted(set(REQUIRED_CATEGORY_IDS) - seen)
    for category_id in missing_required:
        _issue(
            issues,
            "missing_required_category",
            "required private-owner evidence category is absent",
            category_id=category_id,
        )

    forbidden_present = sorted(FORBIDDEN_REQUIRED_CATEGORY_IDS & seen)
    for category_id in forbidden_present:
        _issue(
            issues,
            "forbidden_sales_category",
            "billing/customer sales category must not be part of the private 10/10 matrix",
            category_id=category_id,
        )

    return issues


def build_summary(data: dict[str, Any], issues: list[EvidenceIssue]) -> dict[str, Any]:
    categories = _categories(data)
    counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    severity_counts = {severity: 0 for severity in sorted(ALLOWED_SEVERITIES)}
    for category in categories:
        status = category.get("status")
        if status in counts:
            counts[status] += 1
        severity = category.get("severity")
        if severity in severity_counts:
            severity_counts[severity] += 1

    blockers = [
        {
            "id": category.get("id"),
            "title": category.get("title"),
            "status": category.get("status"),
            "severity": category.get("severity"),
            "next_action": category.get("next_action"),
        }
        for category in categories
        if category.get("blocks_live_trading") is True
        and category.get("status") != "verified"
    ]

    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "ok": not errors,
        "category_count": len(categories),
        "counts": counts,
        "severity_counts": severity_counts,
        "live_blocker_count": len(blockers),
        "live_blockers": blockers,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(issue) for issue in issues],
    }


def strict_failed(issues: list[EvidenceIssue]) -> bool:
    strict_codes = {
        "live_blocker_not_verified",
        "missing_evidence_file",
        "missing_required_field",
        "unknown_status",
    }
    return any(issue.severity == "error" or issue.code in strict_codes for issue in issues)


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_10_10_evidence: private-owner matrix",
        f"schema_ok={str(summary['ok']).lower()} categories={summary['category_count']}",
        "statuses="
        + ", ".join(f"{key}:{value}" for key, value in summary["counts"].items()),
        f"live_blockers={summary['live_blocker_count']}",
    ]
    for issue in summary["issues"]:
        label = issue["severity"].upper()
        category = f" {issue['category_id']}" if issue["category_id"] else ""
        lines.append(f"{label} {issue['code']}{category}: {issue['message']}")
    return "\n".join(lines)


def render_markdown(data: dict[str, Any], summary: dict[str, Any]) -> str:
    lines = [
        "# Evidence Status Report",
        "",
        "Status: automatisch erzeugt aus `docs/production_10_10/evidence_matrix.yaml`.",
        "",
        "## Summary",
        "",
        f"- Kategorien: {summary['category_count']}",
        f"- Live-Blocker nicht verified: {summary['live_blocker_count']}",
        f"- Schema-Fehler: {summary['error_count']}",
        f"- Warnungen: {summary['warning_count']}",
        "",
        "## Status Counts",
        "",
        "| Status | Anzahl |",
        "| --- | ---: |",
    ]
    for status, count in summary["counts"].items():
        lines.append(f"| `{status}` | {count} |")

    lines.extend(
        [
            "",
            "## Live-Blocker",
            "",
            "| ID | Titel | Status | Severity | Naechste Aktion |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for blocker in summary["live_blockers"]:
        lines.append(
            "| {id} | {title} | `{status}` | {severity} | {next_action} |".format(
                id=blocker["id"],
                title=blocker["title"],
                status=blocker["status"],
                severity=blocker["severity"],
                next_action=blocker["next_action"],
            )
        )
    if not summary["live_blockers"]:
        lines.append("| - | Keine nicht-verifizierten Live-Blocker | - | - | - |")

    lines.extend(
        [
            "",
            "## Kategorien",
            "",
            "| ID | Status | Blockiert Live | Evidence-Dateien |",
            "| --- | --- | --- | --- |",
        ]
    )
    for category in _categories(data):
        evidence_files = ", ".join(f"`{item}`" for item in category.get("evidence_files", []))
        lines.append(
            "| {id} | `{status}` | {blocks} | {evidence} |".format(
                id=category.get("id"),
                status=category.get("status"),
                blocks="ja" if category.get("blocks_live_trading") else "nein",
                evidence=evidence_files or "-",
            )
        )

    lines.extend(
        [
            "",
            "## Issues",
            "",
        ]
    )
    if summary["issues"]:
        for issue in summary["issues"]:
            category = f" `{issue['category_id']}`" if issue["category_id"] else ""
            lines.append(
                f"- {issue['severity'].upper()} `{issue['code']}`{category}: {issue['message']}"
            )
    else:
        lines.append("- Keine Issues.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args(argv)

    try:
        data = load_matrix(args.matrix)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        payload = {
            "ok": False,
            "category_count": 0,
            "counts": {},
            "severity_counts": {},
            "live_blocker_count": 0,
            "live_blockers": [],
            "error_count": 1,
            "warning_count": 0,
            "issues": [
                asdict(
                    EvidenceIssue(
                        severity="error",
                        code="matrix_load_failed",
                        category_id=None,
                        message=str(exc),
                    )
                )
            ],
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ERROR matrix_load_failed: {exc}", file=sys.stderr)
        return 1

    issues = validate_matrix(data, root=ROOT)
    summary = build_summary(data, issues)

    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(render_markdown(data, summary), encoding="utf-8")

    if args.json:
        print(json.dumps({"categories": _categories(data), **summary}, indent=2, sort_keys=True))
    else:
        print(render_text(summary))

    if summary["error_count"]:
        return 1
    if args.strict and strict_failed(issues):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
