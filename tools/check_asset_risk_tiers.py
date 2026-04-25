#!/usr/bin/env python3
"""Static checks for asset risk tiers and order sizing deliverables."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "asset_risk_tiers_and_leverage_caps.md"
RISK_TIER_LOGIC_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "asset_risk_tiers.py"
RISK_GOVERNOR_PATH = ROOT / "services" / "signal-engine" / "src" / "signal_engine" / "risk_governor.py"
MATRIX_PATH = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
ASSET_GOV_DOC_PATH = ROOT / "docs" / "production_10_10" / "asset_quarantine_and_live_allowlist.md"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
TEST_PATHS = (
    ROOT / "tests" / "tools" / "test_check_asset_risk_tiers.py",
    ROOT / "tests" / "risk" / "test_asset_risk_tiers.py",
    ROOT / "tests" / "security" / "test_asset_risk_live_caps.py",
)
UNSAFE_LIVE_PHRASES = (
    "alle assets automatisch livefaehig",
    "alle assets automatisch livefähig",
    "all assets automatically live",
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


def analyze_asset_risk_tiers() -> dict[str, Any]:
    issues: list[CheckerIssue] = []
    doc_text = DOC_PATH.read_text(encoding="utf-8").lower() if DOC_PATH.is_file() else ""

    if not DOC_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="doc_missing",
            message="Missing docs/production_10_10/asset_risk_tiers_and_order_sizing.md.",
            path=DOC_PATH,
        )
    if not RISK_TIER_LOGIC_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="asset_risk_logic_missing",
            message="Missing shared/python/src/shared_py/asset_risk_tiers.py.",
            path=RISK_TIER_LOGIC_PATH,
        )
    if not RISK_GOVERNOR_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="risk_governor_missing",
            message="Missing services/signal-engine/src/signal_engine/risk_governor.py.",
            path=RISK_GOVERNOR_PATH,
        )
    for test_path in TEST_PATHS:
        if not test_path.is_file():
            _issue(
                issues,
                severity="error",
                code="test_missing",
                message="Required asset-risk-tier test missing.",
                path=test_path,
            )

    matrix_has_category = False
    if MATRIX_PATH.is_file():
        matrix = _load_yaml(MATRIX_PATH)
        categories = matrix.get("categories")
        if isinstance(categories, list):
            matrix_has_category = any(
                isinstance(item, dict) and str(item.get("id")) == "asset_risk_tiers"
                for item in categories
            )
    if not matrix_has_category:
        _issue(
            issues,
            severity="warning",
            code="matrix_reference_missing",
            message="Evidence matrix does not reference asset_risk_tiers.",
            path=MATRIX_PATH,
        )

    if not ASSET_GOV_DOC_PATH.is_file():
        _issue(
            issues,
            severity="error",
            code="asset_governance_doc_missing",
            message="Missing docs/production_10_10/asset_quarantine_and_live_allowlist.md.",
            path=ASSET_GOV_DOC_PATH,
        )
    if MAIN_CONSOLE_DOC_PATH.is_file():
        main_console_text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        if "asset-risk" not in main_console_text and "risk-tier" not in main_console_text:
            _issue(
                issues,
                severity="error",
                code="main_console_risk_tier_missing",
                message="Main-Console-Doku erwaehnt Asset-Risk-Tiers nicht.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="main_console_doc_missing",
            message="Missing docs/production_10_10/main_console_product_direction.md.",
            path=MAIN_CONSOLE_DOC_PATH,
        )
    if NO_GO_DOC_PATH.is_file():
        no_go_text = NO_GO_DOC_PATH.read_text(encoding="utf-8").lower()
        has_unknown = "unknown" in no_go_text
        has_high_risk = (
            ("hochrisk" in no_go_text)
            or ("tier 4" in no_go_text)
            or ("tier 5" in no_go_text)
            or ("tier d" in no_go_text)
            or ("tier e" in no_go_text)
        )
        if not (has_unknown and has_high_risk):
            _issue(
                issues,
                severity="error",
                code="no_go_high_risk_reference_missing",
                message="No-Go-Regeln erwaehnen unknown/high-risk Assets nicht klar genug.",
                path=NO_GO_DOC_PATH,
            )
    else:
        _issue(
            issues,
            severity="error",
            code="no_go_doc_missing",
            message="Missing docs/production_10_10/no_go_rules.md.",
            path=NO_GO_DOC_PATH,
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

    errors = [item for item in issues if item.severity == "error"]
    warnings = [item for item in issues if item.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "doc_exists": DOC_PATH.is_file(),
        "risk_tier_logic_exists": RISK_TIER_LOGIC_PATH.is_file(),
        "risk_governor_exists": RISK_GOVERNOR_PATH.is_file(),
        "matrix_has_asset_risk_tiers": matrix_has_category,
        "issues": [asdict(item) for item in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_asset_risk_tiers: evidence surface",
        (
            f"ok={str(summary['ok']).lower()} "
            f"doc_exists={summary['doc_exists']} "
            f"risk_tier_logic_exists={summary['risk_tier_logic_exists']} "
            f"risk_governor_exists={summary['risk_governor_exists']}"
        ),
        "matrix_has_asset_risk_tiers=" + str(summary["matrix_has_asset_risk_tiers"]).lower(),
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

    summary = analyze_asset_risk_tiers()
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
