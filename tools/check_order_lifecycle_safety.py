#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "order_lifecycle_exit_emergency_safety.md"
    drill = ROOT / "scripts" / "order_lifecycle_safety_drill.py"
    test_script = ROOT / "tests" / "scripts" / "test_order_lifecycle_safety_drill.py"
    test_idem = ROOT / "tests" / "security" / "test_order_lifecycle_idempotency.py"
    test_exit = ROOT / "tests" / "security" / "test_exit_reduce_only_emergency.py"
    test_tool = ROOT / "tests" / "tools" / "test_check_order_lifecycle_safety.py"
    live_doc = ROOT / "services" / "live-broker" / "README.md"
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"

    for path, code, msg in (
        (doc, "doc_missing", "Order-Lifecycle-Doku fehlt."),
        (drill, "drill_missing", "Safety-Drill-Skript fehlt."),
        (test_script, "script_test_missing", "Script-Test fehlt."),
        (test_idem, "idempotency_test_missing", "Idempotency-Test fehlt."),
        (test_exit, "exit_test_missing", "Exit-/Emergency-Test fehlt."),
        (test_tool, "tool_test_missing", "Tool-Test fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": msg, "path": str(path)})

    if live_doc.is_file():
        text = live_doc.read_text(encoding="utf-8").lower()
        if "order" not in text or "idempot" not in text:
            issues.append({"severity": "error", "code": "live_broker_order_lifecycle_missing", "message": "Live-Broker-Doku referenziert Order-Lifecycle/Idempotency nicht.", "path": str(live_doc)})
    else:
        issues.append({"severity": "error", "code": "live_broker_doc_missing", "message": "Live-Broker-README fehlt.", "path": str(live_doc)})

    if main_console.is_file():
        text = main_console.read_text(encoding="utf-8").lower()
        if "order-state" not in text and "order state" not in text and "order-lifecycle" not in text:
            issues.append({"severity": "error", "code": "main_console_order_state_missing", "message": "Main-Console-Doku referenziert Order-States nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "unknown" not in text or "duplicate" not in text:
            issues.append({"severity": "error", "code": "no_go_unknown_duplicate_missing", "message": "No-Go-Regeln erwaehnen unknown submit state / duplicate orders nicht ausreichend.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    errors = sum(1 for i in issues if i["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Order-Lifecycle-Safety-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"check_order_lifecycle_safety: ok={str(payload['ok']).lower()} errors={payload['error_count']} warnings={payload['warning_count']}")
        for item in payload["issues"]:
            print(f"{item['severity'].upper()} {item['code']}: {item['message']} [{item['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
