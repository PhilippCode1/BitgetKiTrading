#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = (
        (ROOT / "docs" / "production_10_10" / "private_deployment_ngrok_staging_safety.md", "doc_missing", "Deployment/ngrok/staging Sicherheitsdoku fehlt."),
        (ROOT / "tools" / "check_private_deployment_safety.py", "tool_missing", "Checker fehlt."),
        (ROOT / "scripts" / "private_deployment_preflight.py", "script_missing", "Preflight-Skript fehlt."),
        (ROOT / "tests" / "tools" / "test_check_private_deployment_safety.py", "tool_test_missing", "Tool-Test fehlt."),
        (ROOT / "tests" / "scripts" / "test_private_deployment_preflight.py", "script_test_missing", "Script-Test fehlt."),
    )
    for p, code, message in required:
        if not p.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(p)})

    script = ROOT / "scripts" / "private_deployment_preflight.py"
    if script.is_file():
        txt = script.read_text(encoding="utf-8")
        for fragment in (
            "--dry-run",
            "--env-file",
            "--mode",
            "--output-md",
            "local_private",
            "local_ngrok_preview",
            "shadow_private",
            "staging_private",
            "production_private",
        ):
            if fragment not in txt:
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_preflight_capability",
                        "message": f"Preflight-Skript fehlt Anforderung: {fragment}",
                        "path": str(script),
                    }
                )

    docs = ROOT / "docs" / "production_10_10" / "private_deployment_ngrok_staging_safety.md"
    if docs.is_file():
        d = docs.read_text(encoding="utf-8").lower()
        for must in (
            "local_private",
            "local_ngrok_preview",
            "shadow_private",
            "staging_private",
            "production_private",
            "ngrok",
            "live_trade_enable",
            "debug",
            "bitget write",
            "main-console-sicherheitsmodus",
        ):
            if must not in d:
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_runtime_profile_doc_fragment",
                        "message": f"Dokumentation enthält Pflichtfragment nicht: {must}",
                        "path": str(docs),
                    }
                )

    errors = [x for x in issues if x["severity"] == "error"]
    warnings = [x for x in issues if x["severity"] == "warning"]
    return {
        "ok": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft private Deployment/ngrok/staging Safety-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_private_deployment_safety: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']}"
        )
        for issue in payload["issues"]:
            print(f"{issue['severity'].upper()} {issue['code']}: {issue['message']} [{issue['path']}]")
    if payload["error_count"] > 0:
        return 1
    if args.strict and payload["warning_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
