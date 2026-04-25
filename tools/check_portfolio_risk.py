#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _exists(path: Path, code: str, message: str, issues: list[dict[str, str]]) -> None:
    if not path.is_file():
        issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "multi_asset_portfolio_risk.md"
    module = ROOT / "shared" / "python" / "src" / "shared_py" / "portfolio_risk_controls.py"
    test_risk = ROOT / "tests" / "risk" / "test_multi_asset_portfolio_risk.py"
    test_sec = ROOT / "tests" / "security" / "test_portfolio_risk_live_blocks.py"
    test_tool = ROOT / "tests" / "tools" / "test_check_portfolio_risk.py"
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"

    _exists(doc, "doc_missing", "Portfolio-Risk-Doku fehlt.", issues)
    _exists(module, "module_missing", "portfolio_risk_controls.py fehlt.", issues)
    _exists(test_risk, "test_missing", "Risk-Test fehlt.", issues)
    _exists(test_sec, "test_missing", "Security-Test fehlt.", issues)
    _exists(test_tool, "test_missing", "Tool-Test fehlt.", issues)

    if doc.is_file():
        text = doc.read_text(encoding="utf-8").lower()
        if "asset_risk_tiers_and_leverage_caps.md" not in text:
            issues.append({"severity": "error", "code": "risk_doc_reference_missing", "message": "Asset-Risk-Doku wird nicht referenziert.", "path": str(doc)})
        if "multi_asset_order_sizing_margin_safety.md" not in text:
            issues.append({"severity": "error", "code": "order_sizing_doc_reference_missing", "message": "Order-Sizing-Doku wird nicht referenziert.", "path": str(doc)})

    if main_console.is_file():
        text = main_console.read_text(encoding="utf-8").lower()
        if "portfolio-risiko" not in text and "portfolio risiko" not in text:
            issues.append({"severity": "error", "code": "main_console_portfolio_missing", "message": "Main-Console-Doku erwaehnt Portfolio-Risk nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "portfolio" not in text:
            issues.append({"severity": "error", "code": "no_go_portfolio_missing", "message": "No-Go-Regeln erwaehnen Portfolio-Risk nicht.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    error_count = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": error_count == 0, "error_count": error_count, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Portfolio-Risk-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_portfolio_risk: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']}"
        )
        for item in payload["issues"]:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']} [{item['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
