#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "main_console_incident_alerting.md"
    page = ROOT / "apps" / "dashboard" / "src" / "app" / "(operator)" / "console" / "incidents" / "page.tsx"
    view_model = ROOT / "apps" / "dashboard" / "src" / "lib" / "operator-alerts-view-model.ts"
    py_module = ROOT / "shared" / "python" / "src" / "shared_py" / "operator_alerts.py"
    nav = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
    sec_test = ROOT / "tests" / "security" / "test_operator_alert_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_main_console_incidents.py"
    main_console_doc = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"

    for path, code, message in (
        (doc, "doc_missing", "Incident-/Alert-Doku fehlt."),
        (page, "page_missing", "Incidents-Main-Console-Seite fehlt."),
        (view_model, "view_model_missing", "operator-alerts-view-model.ts fehlt."),
        (py_module, "python_module_missing", "operator_alerts.py fehlt."),
        (sec_test, "security_test_missing", "Security-Contract-Test fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if nav.is_file():
        nav_text = nav.read_text(encoding="utf-8")
        if "/incidents" not in nav_text:
            issues.append(
                {
                    "severity": "error",
                    "code": "nav_missing",
                    "message": "Main-Console-Navigation enthält incidents nicht.",
                    "path": str(nav),
                }
            )
    else:
        issues.append({"severity": "error", "code": "nav_file_missing", "message": "Navigationsdatei fehlt.", "path": str(nav)})

    if main_console_doc.is_file():
        mcd = main_console_doc.read_text(encoding="utf-8").lower()
        if "vorfälle" not in mcd and "vorfaelle" not in mcd and "incident" not in mcd:
            issues.append(
                {
                    "severity": "error",
                    "code": "main_console_doc_missing_incidents",
                    "message": "Main-Console-Doku erwähnt Incidents/Vorfälle nicht.",
                    "path": str(main_console_doc),
                }
            )
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console_doc)})

    errors = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Main-Console-Incident-/Alert-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_main_console_incidents: ok={str(payload['ok']).lower()} "
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
