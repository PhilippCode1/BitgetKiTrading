#!/usr/bin/env python3
"""Static checks fuer Multi-Asset-Order-Sizing/Margin-Safety."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "multi_asset_order_sizing_margin_safety.md"
MODULE_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "order_sizing.py"
RISK_DOC_PATH = ROOT / "docs" / "production_10_10" / "asset_risk_tiers_and_leverage_caps.md"
INSTRUMENT_DOC_PATH = ROOT / "docs" / "production_10_10" / "instrument_precision_order_contract.md"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
NO_GO_DOC_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
TEST_PATHS = (
    ROOT / "tests" / "risk" / "test_multi_asset_order_sizing.py",
    ROOT / "tests" / "security" / "test_order_sizing_live_blocks.py",
    ROOT / "tests" / "tools" / "test_check_order_sizing_safety.py",
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _issue(issues: list[Issue], *, severity: str, code: str, message: str, path: Path | None = None) -> None:
    issues.append(Issue(severity=severity, code=code, message=message, path=str(path) if path else None))


def analyze() -> dict[str, Any]:
    issues: list[Issue] = []
    for path, code, message in (
        (DOC_PATH, "doc_missing", "Order-Sizing-Doku fehlt."),
        (MODULE_PATH, "module_missing", "order_sizing.py fehlt."),
        (RISK_DOC_PATH, "risk_doc_missing", "Risk-Tier-Doku fehlt."),
        (INSTRUMENT_DOC_PATH, "instrument_doc_missing", "Instrument-Contract-Doku fehlt."),
    ):
        if not path.is_file():
            _issue(issues, severity="error", code=code, message=message, path=path)
    for path in TEST_PATHS:
        if not path.is_file():
            _issue(issues, severity="error", code="test_missing", message="Erforderlicher Test fehlt.", path=path)

    if MAIN_CONSOLE_DOC_PATH.is_file():
        text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        if "order-sizing" not in text and "order sizing" not in text:
            _issue(
                issues,
                severity="error",
                code="main_console_order_sizing_missing",
                message="Main-Console-Doku erwaehnt Order-Sizing nicht.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="main_console_doc_missing", message="Main-Console-Doku fehlt.", path=MAIN_CONSOLE_DOC_PATH)

    if NO_GO_DOC_PATH.is_file():
        text = NO_GO_DOC_PATH.read_text(encoding="utf-8").lower()
        if not ("positionsgro" in text or "ordergroesse" in text or "notional" in text):
            _issue(
                issues,
                severity="error",
                code="no_go_order_size_missing",
                message="No-Go-Regeln erwaehnen unsichere Positionsgroesse nicht.",
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
            f"check_order_sizing_safety: ok={str(summary['ok']).lower()} "
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
