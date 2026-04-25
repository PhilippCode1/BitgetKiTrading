#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "live_broker_multi_asset_preflight.md"
    module = ROOT / "shared" / "python" / "src" / "shared_py" / "live_preflight.py"
    sec_test = ROOT / "tests" / "security" / "test_live_broker_multi_asset_preflight.py"
    lb_test = ROOT / "tests" / "live_broker" / "test_live_preflight_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_live_broker_preflight.py"
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"
    live_broker_service = ROOT / "services" / "live-broker" / "src" / "live_broker" / "orders" / "service.py"

    for path, code, message in (
        (doc, "doc_missing", "Live-Preflight-Doku fehlt."),
        (module, "module_missing", "live_preflight.py fehlt."),
        (sec_test, "security_test_missing", "Security-Tests fehlen."),
        (lb_test, "live_broker_test_missing", "Live-Broker-Contract-Tests fehlen."),
        (tool_test, "tool_test_missing", "Tool-Tests fehlen."),
        (live_broker_service, "live_broker_missing", "Live-Broker-Service fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "preflight" not in text:
            issues.append({"severity": "error", "code": "no_go_preflight_missing", "message": "No-Go-Regeln erwaehnen Preflight nicht.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    if main_console.is_file():
        text = main_console.read_text(encoding="utf-8").lower()
        if "preflight" not in text:
            issues.append({"severity": "error", "code": "main_console_preflight_missing", "message": "Main-Console-Doku erwaehnt Preflight-Blockgruende nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    error_count = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": error_count == 0, "error_count": error_count, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Live-Broker-Multi-Asset-Preflight-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_live_broker_preflight: ok={str(payload['ok']).lower()} "
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
