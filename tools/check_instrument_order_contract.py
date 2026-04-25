#!/usr/bin/env python3
"""Checks Instrument Precision/Order Contract deliverables."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "production_10_10" / "instrument_precision_order_contract.md"
CONTRACT_PATH = ROOT / "shared" / "python" / "src" / "shared_py" / "bitget" / "order_contract.py"
NO_GO_PATH = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
ASSET_UNIVERSE_DOC_PATH = ROOT / "docs" / "production_10_10" / "bitget_asset_universe.md"
MAIN_CONSOLE_DOC_PATH = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
TEST_PATHS = (
    ROOT / "tests" / "shared" / "test_instrument_order_contract.py",
    ROOT / "tests" / "security" / "test_order_parameter_fail_closed.py",
    ROOT / "tests" / "tools" / "test_check_instrument_order_contract.py",
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
    if not DOC_PATH.is_file():
        _issue(issues, severity="error", code="doc_missing", message="Instrument-Contract-Doku fehlt.", path=DOC_PATH)
    if not CONTRACT_PATH.is_file():
        _issue(issues, severity="error", code="contract_missing", message="order_contract.py fehlt.", path=CONTRACT_PATH)
    for path in TEST_PATHS:
        if not path.is_file():
            _issue(issues, severity="error", code="test_missing", message="Erforderlicher Test fehlt.", path=path)
    if NO_GO_PATH.is_file():
        text = NO_GO_PATH.read_text(encoding="utf-8").lower()
        if not ("precision" in text and "asset-freigabe" in text):
            _issue(
                issues,
                severity="error",
                code="no_go_reference_missing",
                message="No-Go-Regeln referenzieren Instrumentkontext nicht ausreichend.",
                path=NO_GO_PATH,
            )
    else:
        _issue(issues, severity="error", code="no_go_doc_missing", message="No-Go-Doku fehlt.", path=NO_GO_PATH)
    if ASSET_UNIVERSE_DOC_PATH.is_file():
        text = ASSET_UNIVERSE_DOC_PATH.read_text(encoding="utf-8").lower()
        if "instrument_precision_order_contract.md" not in text:
            _issue(
                issues,
                severity="error",
                code="asset_universe_contract_link_missing",
                message="Asset-Universe-Doku referenziert Instrument-Order-Contract nicht.",
                path=ASSET_UNIVERSE_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="asset_universe_doc_missing", message="Asset-Universe-Doku fehlt.", path=ASSET_UNIVERSE_DOC_PATH)
    if MAIN_CONSOLE_DOC_PATH.is_file():
        text = MAIN_CONSOLE_DOC_PATH.read_text(encoding="utf-8").lower()
        has_precision = "precision" in text
        has_block_reason = ("blockgrund" in text) or ("blockgruend" in text) or ("blockgr" in text)
        if not (has_precision and has_block_reason):
            _issue(
                issues,
                severity="error",
                code="main_console_precision_missing",
                message="Main-Console-Doku erwaehnt Precision/Blockgruende nicht.",
                path=MAIN_CONSOLE_DOC_PATH,
            )
    else:
        _issue(issues, severity="error", code="main_console_doc_missing", message="Main-Console-Doku fehlt.", path=MAIN_CONSOLE_DOC_PATH)

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
            f"check_instrument_order_contract: ok={str(summary['ok']).lower()} "
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
