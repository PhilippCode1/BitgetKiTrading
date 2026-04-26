#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMAS_EXEC_AUTH_NONE: tuple[tuple[str, Path], ...] = (
    ("assistant_turn.schema.json", ROOT / "shared" / "contracts" / "schemas" / "assistant_turn.schema.json"),
    ("operator_explain.schema.json", ROOT / "shared" / "contracts" / "schemas" / "operator_explain.schema.json"),
)


def _schema_requires_execution_authority_none(label: str, path: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not path.is_file():
        out.append(
            {
                "severity": "error",
                "code": "llm_schema_missing",
                "message": f"Contract-Schema fehlt ({label}).",
                "path": str(path),
            }
        )
        return out
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        out.append(
            {
                "severity": "error",
                "code": "llm_schema_json_invalid",
                "message": f"Schema nicht parsebar ({label}): {exc}",
                "path": str(path),
            }
        )
        return out
    req = data.get("required")
    if not isinstance(req, list) or "execution_authority" not in req:
        out.append(
            {
                "severity": "error",
                "code": "llm_schema_execution_authority_not_required",
                "message": f"Schema muss execution_authority als required haben ({label}).",
                "path": str(path),
            }
        )
    props = data.get("properties")
    spec = props.get("execution_authority") if isinstance(props, dict) else None
    if (
        not isinstance(spec, dict)
        or spec.get("type") != "string"
        or spec.get("const") != "none"
    ):
        out.append(
            {
                "severity": "error",
                "code": "llm_schema_execution_authority_const_invalid",
                "message": (
                    f"execution_authority muss type=string und const=none sein ({label})."
                ),
                "path": str(path),
            }
        )
    return out


def analyze() -> dict[str, object]:
    issues: list[dict[str, str]] = []
    doc = ROOT / "docs" / "production_10_10" / "main_console_ai_operator_assistant.md"
    schema_doc = ROOT / "docs" / "production_10_10" / "ai_operator_assistant_prompt_schema.md"
    sec_test = ROOT / "tests" / "security" / "test_ai_operator_assistant_contracts.py"
    tool_test = ROOT / "tests" / "tools" / "test_check_ai_operator_assistant_safety.py"
    py_contract = ROOT / "shared" / "python" / "src" / "shared_py" / "ai_operator_assistant.py"
    op_err = ROOT / "apps" / "dashboard" / "src" / "lib" / "operator-explain-errors.ts"
    saf_err = ROOT / "apps" / "dashboard" / "src" / "lib" / "safety-diagnosis-errors.ts"
    op_panel = ROOT / "apps" / "dashboard" / "src" / "components" / "panels" / "OperatorExplainPanel.tsx"
    saf_panel = ROOT / "apps" / "dashboard" / "src" / "components" / "panels" / "SafetyDiagnosisPanel.tsx"

    for path, code, message in (
        (doc, "doc_missing", "AI-Operator-Assistent-Doku fehlt."),
        (schema_doc, "schema_doc_missing", "Prompt-/Schema-Doku fehlt."),
        (sec_test, "security_test_missing", "Security-Contract-Test fehlt."),
        (tool_test, "tool_test_missing", "Tool-Test fehlt."),
        (py_contract, "python_contract_missing", "Python-AI-Safety-Contract fehlt."),
    ):
        if not path.is_file():
            issues.append({"severity": "error", "code": code, "message": message, "path": str(path)})

    if op_err.is_file():
        txt = op_err.read_text(encoding="utf-8")
        if 'authority === "none"' not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "execution_authority_rule_missing",
                    "message": "operator-explain-success prüft execution_authority=none nicht.",
                    "path": str(op_err),
                }
            )
    else:
        issues.append({"severity": "error", "code": "operator_explain_guard_missing", "message": "operator-explain-errors.ts fehlt.", "path": str(op_err)})

    if saf_err.is_file():
        txt = saf_err.read_text(encoding="utf-8")
        if 'o.execution_authority === "none"' not in txt:
            issues.append(
                {
                    "severity": "error",
                    "code": "safety_execution_authority_rule_missing",
                    "message": "safety-diagnosis-success prüft execution_authority=none nicht.",
                    "path": str(saf_err),
                }
            )
    else:
        issues.append({"severity": "error", "code": "safety_guard_missing", "message": "safety-diagnosis-errors.ts fehlt.", "path": str(saf_err)})

    for label, schema_path in SCHEMAS_EXEC_AUTH_NONE:
        issues.extend(_schema_requires_execution_authority_none(label, schema_path))

    degraded_phrase = "aiAssistantDegradedSafe"
    for panel, code in ((op_panel, "operator_panel_degraded_missing"), (saf_panel, "safety_panel_degraded_missing")):
        if panel.is_file():
            if degraded_phrase not in panel.read_text(encoding="utf-8"):
                issues.append(
                    {
                        "severity": "error",
                        "code": code,
                        "message": "Degraded-Safety-Hinweis in UI fehlt.",
                        "path": str(panel),
                    }
                )

    errors = sum(1 for item in issues if item["severity"] == "error")
    return {"ok": errors == 0, "error_count": errors, "warning_count": 0, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prüft Safety-Vertrag des KI-Operator-Assistenten.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_ai_operator_assistant_safety: ok={str(payload['ok']).lower()} "
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
