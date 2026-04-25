#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "reconcile_exchange_truth_per_asset.md"
    script = ROOT / "scripts" / "reconcile_truth_drill.py"
    sec_test = ROOT / "tests" / "security" / "test_reconcile_exchange_truth_blocks.py"
    script_test = ROOT / "tests" / "scripts" / "test_reconcile_truth_drill.py"
    lb_test = ROOT / "tests" / "live_broker" / "test_reconcile_truth_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_reconcile_truth.py"
    lb_doc = ROOT / "services" / "live-broker" / "README.md"
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"

    for path, code, msg in (
        (doc, "doc_missing", "Reconcile-Truth-Doku fehlt."),
        (script, "drill_missing", "Reconcile-Drill-Skript fehlt."),
        (sec_test, "security_test_missing", "Security-Test fehlt."),
        (script_test, "script_test_missing", "Script-Test fehlt."),
        (lb_test, "live_broker_test_missing", "Live-Broker-Contract-Test fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": msg, "path": str(path)})

    if lb_doc.is_file():
        if "reconcile" not in lb_doc.read_text(encoding="utf-8").lower():
            issues.append({"severity": "error", "code": "live_broker_doc_reconcile_missing", "message": "Live-Broker-Doku referenziert Reconcile nicht.", "path": str(lb_doc)})
    else:
        issues.append({"severity": "error", "code": "live_broker_doc_missing", "message": "Live-Broker-README fehlt.", "path": str(lb_doc)})

    if main_console.is_file():
        if "reconcile" not in main_console.read_text(encoding="utf-8").lower():
            issues.append({"severity": "error", "code": "main_console_reconcile_missing", "message": "Main-Console-Doku referenziert Reconcile nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "reconcile-fail" not in text and "reconcile" not in text:
            issues.append({"severity": "error", "code": "no_go_reconcile_missing", "message": "No-Go-Regeln erwaehnen Reconcile-Fail nicht.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    errors = sum(1 for i in issues if i["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Reconcile-Truth-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"check_reconcile_truth: ok={str(payload['ok']).lower()} errors={payload['error_count']} warnings={payload['warning_count']}")
        for item in payload["issues"]:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']} [{item['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
