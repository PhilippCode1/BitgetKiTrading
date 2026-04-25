#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WELCOME_PAGE = ROOT / "apps" / "dashboard" / "src" / "app" / "welcome" / "page.tsx"
PUBLIC_ROOT_PAGE = ROOT / "apps" / "dashboard" / "src" / "app" / "(public)" / "page.tsx"
RETURN_TO_LIB = ROOT / "apps" / "dashboard" / "src" / "lib" / "return-to-safety.ts"
ENTRY_DOC = ROOT / "docs" / "production_10_10" / "single_admin_entry_flow.md"

FORBIDDEN_TERMS = ("billing", "customer", "pricing", "sales", "tenant")


def _missing(path: Path, issues: list[dict[str, str]], code: str, message: str) -> None:
    if not path.is_file():
        issues.append(
            {"severity": "error", "code": code, "message": message, "path": str(path)}
        )


def analyze() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    for path, code, message in (
        (WELCOME_PAGE, "welcome_missing", "Welcome-Seite fehlt."),
        (PUBLIC_ROOT_PAGE, "root_page_missing", "Root-Seite fehlt."),
        (RETURN_TO_LIB, "return_to_lib_missing", "ReturnTo-Sicherheitsmodul fehlt."),
        (ENTRY_DOC, "entry_doc_missing", "Single-Admin-Entry-Doku fehlt."),
    ):
        _missing(path, issues, code, message)

    if WELCOME_PAGE.is_file():
        text = WELCOME_PAGE.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN_TERMS:
            if term in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "forbidden_term_in_welcome",
                        "message": f"Verbotener Begriff in Welcome-Seite: {term}",
                        "path": str(WELCOME_PAGE),
                    }
                )

    if PUBLIC_ROOT_PAGE.is_file():
        text = PUBLIC_ROOT_PAGE.read_text(encoding="utf-8")
        if "redirect(CONSOLE_BASE)" not in text:
            issues.append(
                {
                    "severity": "error",
                    "code": "root_redirect_missing",
                    "message": "Root-Seite leitet nicht kanonisch auf /console um.",
                    "path": str(PUBLIC_ROOT_PAGE),
                }
            )

    if RETURN_TO_LIB.is_file():
        text = RETURN_TO_LIB.read_text(encoding="utf-8")
        required_snippets = (
            "https?:)?\\/\\/",
            'return `${CONSOLE_BASE}/ops`',
            "safePathname === \"/\"",
        )
        for snippet in required_snippets:
            if snippet not in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "return_to_rule_missing",
                        "message": f"ReturnTo-Regel fehlt: {snippet}",
                        "path": str(RETURN_TO_LIB),
                    }
                )

    if ENTRY_DOC.is_file():
        text = ENTRY_DOC.read_text(encoding="utf-8").lower()
        required_topics = (
            "zielroute",
            "auth-annahme",
            "returnto-regeln",
            "open-redirect-schutz",
            "single-admin-betrieb",
            "no-go",
        )
        for topic in required_topics:
            if topic not in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "entry_doc_topic_missing",
                        "message": f"Doku-Thema fehlt: {topic}",
                        "path": str(ENTRY_DOC),
                    }
                )

    errors = [i for i in issues if i["severity"] == "error"]
    return {
        "ok": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": 0,
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check single-admin entry flow surface.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_single_admin_entry_flow: ok={str(payload['ok']).lower()} "
            f"errors={payload['error_count']} warnings={payload['warning_count']}"
        )
        for issue in payload["issues"]:
            print(
                f"{issue['severity'].upper()} {issue['code']}: {issue['message']} [{issue.get('path','')}]"
            )
    if not args.strict:
        return 0
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
