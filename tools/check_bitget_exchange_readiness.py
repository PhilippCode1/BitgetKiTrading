#!/usr/bin/env python3
"""Static checker for Bitget Exchange Readiness deliverables."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOC = Path("docs/production_10_10/bitget_exchange_readiness.md")
SCRIPT = Path("scripts/bitget_readiness_check.py")
TOOL = Path("tools/check_bitget_exchange_readiness.py")
SCRIPT_TEST = Path("tests/scripts/test_bitget_readiness_check.py")
SECURITY_TEST = Path("tests/security/test_bitget_exchange_readiness_contracts.py")
TOOL_TEST = Path("tests/tools/test_check_bitget_exchange_readiness.py")
EVIDENCE = Path("docs/production_10_10/evidence_matrix.yaml")
NO_GO = Path("docs/production_10_10/no_go_rules.md")

STATUS_ERROR = "error"

REQUIRED_DOC_TERMS = (
    "zielbild",
    "read-only",
    "write",
    "demo",
    "live",
    "api-version",
    "permissions",
    "withdrawal",
    "server-time",
    "rate-limit",
    "instrument discovery",
    "live-gates",
    "no-go",
    "tests",
)

SECRET_PATTERNS = (
    re.compile(r"sk-(?:live|test|proj)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\b[A-Za-z0-9+/=]{40,}\b"),
)


@dataclass(frozen=True)
class CheckIssue:
    severity: str
    code: str
    message: str


def _issue(issues: list[CheckIssue], code: str, message: str) -> None:
    issues.append(CheckIssue(STATUS_ERROR, code, message))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate(root: Path = ROOT, *, strict: bool = False) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    required = (DOC, SCRIPT, TOOL, SCRIPT_TEST, SECURITY_TEST, TOOL_TEST)
    for rel in required:
        if not (root / rel).is_file():
            _issue(issues, "required_file_missing", f"missing {rel.as_posix()}")
    if not (root / EVIDENCE).is_file():
        _issue(issues, "evidence_missing", f"missing {EVIDENCE.as_posix()}")
    if not (root / NO_GO).is_file():
        _issue(issues, "no_go_missing", f"missing {NO_GO.as_posix()}")

    if (root / DOC).is_file():
        doc = _read(root / DOC).lower()
        for term in REQUIRED_DOC_TERMS:
            if term not in doc:
                _issue(issues, "doc_term_missing", f"doc missing term: {term}")
        for pattern in SECRET_PATTERNS:
            if pattern.search(doc):
                _issue(issues, "doc_secret_like_value", "doc contains secret-like value")

    if (root / SCRIPT).is_file():
        script = _read(root / SCRIPT).lower()
        forbidden_calls = ("place_order(", "cancel_order(", "replace_order(", "submit_order(")
        for call in forbidden_calls:
            if call in script:
                _issue(issues, "script_write_call_forbidden", f"readiness script contains {call}")
        for required_phrase in ("dry-run", "readonly", "demo-safe", "live_write_allowed"):
            if required_phrase not in script:
                _issue(issues, "script_mode_missing", f"script missing {required_phrase}")

    if (root / EVIDENCE).is_file():
        evidence = _read(root / EVIDENCE)
        for ref in (
            "docs/production_10_10/bitget_exchange_readiness.md",
            "scripts/bitget_readiness_check.py",
            "tools/check_bitget_exchange_readiness.py",
            "tests/scripts/test_bitget_readiness_check.py",
            "tests/security/test_bitget_exchange_readiness_contracts.py",
            "tests/tools/test_check_bitget_exchange_readiness.py",
        ):
            if ref not in evidence:
                _issue(issues, "evidence_reference_missing", f"evidence matrix missing {ref}")

    if (root / NO_GO).is_file():
        no_go = _read(root / NO_GO).lower()
        for term in ("bitget readiness", "withdrawal", "api-version"):
            if term not in no_go:
                _issue(issues, "no_go_term_missing", f"No-Go rules missing {term}")

    if strict and (root / SCRIPT).is_file():
        script = _read(root / SCRIPT)
        if "WRITE_ORDER_ALLOWED_DEFAULT" not in script:
            _issue(issues, "write_default_missing", "script must import/use WRITE_ORDER_ALLOWED_DEFAULT")
    return issues


def summary(issues: list[CheckIssue], *, strict: bool) -> dict[str, Any]:
    return {
        "ok": not issues,
        "strict": strict,
        "error_count": len(issues),
        "issues": [asdict(issue) for issue in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    issues = validate(args.root, strict=args.strict)
    payload = summary(issues, strict=args.strict)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        mode = "strict" if args.strict else "default"
        print(f"bitget_exchange_readiness_check: mode={mode}")
        print(f"ok={str(payload['ok']).lower()} errors={payload['error_count']}")
        for issue in issues:
            print(f"{issue.severity.upper()} {issue.code}: {issue.message}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
