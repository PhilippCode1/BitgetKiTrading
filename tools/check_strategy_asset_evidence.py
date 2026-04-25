#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "strategy_evidence_per_asset_class.md"
    module = ROOT / "shared" / "python" / "src" / "shared_py" / "strategy_asset_evidence.py"
    script = ROOT / "scripts" / "strategy_asset_evidence_report.py"
    fixture = ROOT / "tests" / "fixtures" / "strategy_asset_evidence_sample.json"
    tests = [
        ROOT / "tests" / "risk" / "test_strategy_asset_evidence.py",
        ROOT / "tests" / "security" / "test_strategy_live_scope_blocks.py",
        ROOT / "tests" / "scripts" / "test_strategy_asset_evidence_report.py",
        ROOT / "tests" / "tools" / "test_check_strategy_asset_evidence.py",
    ]
    main_console = ROOT / "docs" / "production_10_10" / "main_console_product_direction.md"
    no_go = ROOT / "docs" / "production_10_10" / "no_go_rules.md"

    for path, code, message in (
        (doc, "doc_missing", "Strategy-Evidence-Doku fehlt."),
        (module, "module_missing", "strategy_asset_evidence.py fehlt."),
        (script, "script_missing", "strategy_asset_evidence_report.py fehlt."),
        (fixture, "fixture_missing", "strategy_asset_evidence_sample.json fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})
    for path in tests:
        if not path.is_file():
            issues.append({"severity": "error", "code": "test_missing", "message": "Erforderlicher Test fehlt.", "path": str(path)})

    if doc.is_file():
        text = doc.read_text(encoding="utf-8").lower()
        if "asset_risk_tiers_and_leverage_caps.md" not in text:
            issues.append({"severity": "error", "code": "risk_doc_reference_missing", "message": "Asset-Risk-Doku wird nicht referenziert.", "path": str(doc)})
        # performance-evidence nur falls vorhanden
        perf_doc = ROOT / "docs" / "production_10_10" / "performance_evidence.md"
        if perf_doc.is_file() and "performance_evidence.md" not in text:
            issues.append({"severity": "error", "code": "performance_doc_reference_missing", "message": "Performance-Evidence-Doku wird nicht referenziert.", "path": str(doc)})

    if main_console.is_file():
        text = main_console.read_text(encoding="utf-8").lower()
        if "strategy evidence" not in text and "strategie-evidence" not in text and "strategie evidence" not in text:
            issues.append({"severity": "error", "code": "main_console_strategy_evidence_missing", "message": "Main-Console-Doku erwaehnt Strategy-Evidence nicht.", "path": str(main_console)})
    else:
        issues.append({"severity": "error", "code": "main_console_doc_missing", "message": "Main-Console-Doku fehlt.", "path": str(main_console)})

    if no_go.is_file():
        text = no_go.read_text(encoding="utf-8").lower()
        if "strategy" not in text and "evidence" not in text:
            issues.append({"severity": "error", "code": "no_go_strategy_evidence_missing", "message": "No-Go-Regeln erwaehnen fehlende Strategy-Evidence nicht.", "path": str(no_go)})
    else:
        issues.append({"severity": "error", "code": "no_go_doc_missing", "message": "No-Go-Doku fehlt.", "path": str(no_go)})

    error_count = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": error_count == 0, "error_count": error_count, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Strategy-Asset-Evidence-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_strategy_asset_evidence: ok={str(payload['ok']).lower()} "
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
