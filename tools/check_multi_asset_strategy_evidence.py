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
        (ROOT / "docs" / "production_10_10" / "multi_asset_strategy_performance_evidence.md", "doc_missing", "Multi-Asset-Evidence-Doku fehlt."),
        (ROOT / "shared" / "python" / "src" / "shared_py" / "multi_asset_strategy_evidence.py", "module_missing", "multi_asset_strategy_evidence.py fehlt."),
        (ROOT / "scripts" / "verify_multi_asset_strategy_evidence.py", "script_missing", "verify_multi_asset_strategy_evidence.py fehlt."),
        (ROOT / "tests" / "scripts" / "test_verify_multi_asset_strategy_evidence.py", "script_test_missing", "Script-Test fehlt."),
        (ROOT / "tests" / "quant" / "test_multi_asset_strategy_evidence.py", "quant_test_missing", "Quant-Test fehlt."),
        (ROOT / "tests" / "tools" / "test_check_multi_asset_strategy_evidence.py", "tool_test_missing", "Tool-Test fehlt."),
        (ROOT / "tests" / "fixtures" / "multi_asset_strategy_evidence_sample.json", "fixture_missing", "Fixture fehlt."),
    )
    for path, code, msg in required:
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": msg, "path": str(path)})

    script = ROOT / "scripts" / "verify_multi_asset_strategy_evidence.py"
    if script.is_file():
        text = script.read_text(encoding="utf-8")
        for fragment in ("--dry-run", "--input-json", "--output-md", "--output-json", "PASS_WITH_WARNINGS", "FAIL"):
            if fragment not in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "script_requirement_missing",
                        "message": f"Script-Anforderung fehlt: {fragment}",
                        "path": str(script),
                    }
                )

    doc = ROOT / "docs" / "production_10_10" / "multi_asset_strategy_performance_evidence.md"
    if doc.is_file():
        d = doc.read_text(encoding="utf-8").lower()
        for klass in (
            "major_high_liquidity",
            "large_liquidity",
            "mid_liquidity",
            "high_volatility",
            "low_liquidity",
            "new_listing",
            "delisting_risk",
            "blocked_unknown",
        ):
            if klass not in d:
                issues.append(
                    {
                        "severity": "error",
                        "code": "asset_class_missing_in_doc",
                        "message": f"Asset-Klasse in Doku fehlt: {klass}",
                        "path": str(doc),
                    }
                )

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    return {"ok": len(errors) == 0, "error_count": len(errors), "warning_count": len(warnings), "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Multi-Asset Strategy-Evidence-Artefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_multi_asset_strategy_evidence: ok={str(payload['ok']).lower()} "
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
