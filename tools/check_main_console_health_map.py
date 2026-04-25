#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "main_console_observability_health_map.md"
    page = ROOT / "apps" / "dashboard" / "src" / "app" / "(operator)" / "console" / "system-health-map" / "page.tsx"
    vm = ROOT / "apps" / "dashboard" / "src" / "lib" / "health-map-view-model.ts"
    py_module = ROOT / "shared" / "python" / "src" / "shared_py" / "health_map.py"
    nav = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
    sec_test = ROOT / "tests" / "security" / "test_health_map_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_main_console_health_map.py"

    for path, code, message in (
        (doc, "doc_missing", "Health-Map-Doku fehlt."),
        (page, "page_missing", "Main-Console-Modul Systemzustand & Datenflüsse fehlt."),
        (vm, "view_model_missing", "health-map-view-model.ts fehlt."),
        (py_module, "python_module_missing", "health_map.py fehlt."),
        (sec_test, "security_test_missing", "Security-Contract-Test fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if nav.is_file():
        txt = nav.read_text(encoding="utf-8")
        if "/system-health-map" not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "nav_missing",
                    "message": "Navigation enthält system-health-map nicht.",
                    "path": str(nav),
                }
            )
    else:
        issues.append({"severity": "error", "code": "nav_file_missing", "message": "Navigationsdatei fehlt.", "path": str(nav)})

    errors = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Main-Console Health-Landkarte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_main_console_health_map: ok={str(payload['ok']).lower()} "
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
