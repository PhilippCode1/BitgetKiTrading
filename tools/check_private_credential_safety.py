#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    required = (
        (ROOT / "docs" / "production_10_10" / "private_bitget_credential_safety.md", "doc_missing", "Credential-Safety-Doku fehlt."),
        (ROOT / "shared" / "python" / "src" / "shared_py" / "private_credentials.py", "contract_missing", "private_credentials.py fehlt."),
        (ROOT / "scripts" / "private_bitget_credential_check.py", "script_missing", "private_bitget_credential_check.py fehlt."),
        (ROOT / "tests" / "security" / "test_private_credential_safety.py", "security_test_missing", "Security-Test fehlt."),
        (ROOT / "tests" / "tools" / "test_check_private_credential_safety.py", "tool_test_missing", "Tool-Test fehlt."),
    )
    for p, code, msg in required:
        if not p.is_file():
            issues.append({"severity": "error", "code": code, "message": msg, "path": str(p)})

    script = ROOT / "scripts" / "private_bitget_credential_check.py"
    if script.is_file():
        txt = script.read_text(encoding="utf-8")
        for flag in ("--dry-run", "--template", "--strict-runtime", "--output-md"):
            if flag not in txt:
                issues.append(
                    {
                        "severity": "error",
                        "code": "script_flag_missing",
                        "message": f"Script unterstützt {flag} nicht.",
                        "path": str(script),
                    }
                )

    live_broker_page = ROOT / "apps" / "dashboard" / "src" / "app" / "(operator)" / "console" / "live-broker" / "page.tsx"
    if live_broker_page.is_file():
        txt = live_broker_page.read_text(encoding="utf-8")
        if "Bitget-Verbindung" not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "ui_module_missing",
                    "message": "Main-Console-Modul 'Bitget-Verbindung' fehlt.",
                    "path": str(live_broker_page),
                }
            )

    errors = sum(1 for i in issues if i["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft private Credential-Safety-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_private_credential_safety: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']}"
        )
        for i in payload["issues"]:
            print(f"{i['severity'].upper()} {i['code']}: {i['message']} [{i['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
