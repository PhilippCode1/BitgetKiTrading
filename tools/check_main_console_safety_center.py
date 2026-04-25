#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "main_console_safety_command_center.md"
    page = ROOT / "apps" / "dashboard" / "src" / "app" / "(operator)" / "console" / "safety-center" / "page.tsx"
    nav = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
    sec_test = ROOT / "tests" / "security" / "test_main_console_safety_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_main_console_safety_center.py"
    main_console_doc = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"

    for path, code, message in (
        (doc, "doc_missing", "Sicherheitszentrale-Doku fehlt."),
        (page, "page_missing", "Safety-Center-Seite fehlt."),
        (sec_test, "security_test_missing", "Security-Contract-Test fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if nav.is_file():
        if "safety-center" not in nav.read_text(encoding="utf-8"):
            issues.append({"severity": "error", "code": "nav_missing", "message": "Main-Console-Navigation enthält safety-center nicht.", "path": str(nav)})
    else:
        issues.append({"severity": "error", "code": "nav_file_missing", "message": "Navigationsdatei fehlt.", "path": str(nav)})

    if main_console_doc.is_file():
        if "sicherheitszentrale" not in main_console_doc.read_text(encoding="utf-8").lower():
            issues.append({"severity": "error", "code": "main_console_doc_missing_center", "message": "Main-Console-Doku erwähnt Sicherheitszentrale nicht.", "path": str(main_console_doc)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console_doc)})

    if no_go.is_file():
        no_go_text = no_go.read_text(encoding="utf-8").lower()
        if "unknown" not in no_go_text or "kill-switch" not in no_go_text:
            issues.append({"severity": "error", "code": "no_go_coverage_missing", "message": "No-Go-Regeln decken kritische Safety-Center-Fälle nicht ausreichend ab.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    errors = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Main-Console-Sicherheitszentrale-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_main_console_safety_center: ok={str(payload['ok']).lower()} "
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
