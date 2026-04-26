#!/usr/bin/env python3
"""Static checker for German-only visible UI labels."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_SRC_DEFAULT = ROOT / "apps" / "dashboard" / "src"
MESSAGES_DIR_DEFAULT = DASHBOARD_SRC_DEFAULT / "messages"
POLICY_DOC_DEFAULT = ROOT / "docs" / "production_10_10" / "german_only_ui_policy.md"
GLOSSARY_DOC_DEFAULT = ROOT / "docs" / "production_10_10" / "german_ui_glossary.md"

CRITICAL_ENGLISH_VISIBLE_PHRASES = (
    "Ops Console",
    "Operator Cockpit",
    "Health & Incidents",
    "Signal-Center",
    "No-Trade",
    "Self Healing",
    "Capability-Matrix",
    "Model-Ops",
    "Live readiness",
    "Operator approval",
)

OUT_OF_SCOPE_VISIBLE_PHRASES = (
    "Billing",
    "Customer",
    "Pricing",
    "Sales",
    "Subscription",
    "Checkout",
    "Payment",
)

GERMAN_MAIN_CONSOLE_TERMS = (
    "Hauptkonsole",
    "Systemzustand",
    "Betreiber",
    "Echtgeldmodus",
    "Papiermodus",
    "Schattenmodus",
    "Not-Stopp",
    "Sicherheits-Sperre",
    "Abgleich",
    "Kein Handel",
    "Quarantäne",
    "Live-Blocker",
)

TECHNICAL_ALLOW_HINTS = (
    "http",
    "/api/",
    "api_",
    "NEXT_PUBLIC_",
    "DASHBOARD_",
    "LIVE_",
    "RISK_",
    "EXECUTION_MODE",
    "data-testid",
    "tenant_",
    "payment_status",
    "billing_",
)


@dataclass(frozen=True)
class UiIssue:
    severity: str
    code: str
    message: str
    path: str | None = None
    line: int | None = None


def _issue(
    issues: list[UiIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
    line: int | None = None,
) -> None:
    issues.append(
        UiIssue(
            severity=severity,
            code=code,
            message=message,
            path=path,
            line=line,
        )
    )


def _looks_technical(line: str) -> bool:
    return any(hint in line for hint in TECHNICAL_ALLOW_HINTS)


def _looks_like_intl_message_key(token: str) -> bool:
    """next-intl/nextjs message keys (z.B. ui.appError.openCustomerPortal) — keine sichtbare Kopie."""
    if "." not in token or " " in token:
        return False
    parts = token.split(".")
    return len(parts) >= 2 and parts[0].isalpha() and all(p.replace("_", "").isalnum() for p in parts)


def _skip_out_of_scope_scan(file_path: Path) -> bool:
    """Legacy-Kunden-/Commerce-Flaechen: keine P1-Warnungen fuer verbotene EN-Marketing-Begriffe."""
    s = str(file_path).replace("\\", "/")
    if "/messages/" in s and s.endswith(".json"):
        return True
    markers = (
        "(customer)",
        "/admin/billing",
        "/admin/commerce-payments",
        "/admin/customers/",
        "/account/billing",
        "portal/account",
        "DepositCheckoutPanel",
        "commerce/customer",
        "CustomerSidebarNav",
        "TelegramAccountPanel",
    )
    return any(m in s for m in markers)


def _extract_candidate_strings(file_path: Path, raw_line: str) -> list[str]:
    line = raw_line.strip()
    if not line:
        return []
    if file_path.suffix == ".json":
        # Nur sichtbare Werte pruefen, keine JSON-Keys.
        return re.findall(r':\s*"([^"]*)"', line)
    # TS/TSX: quoted literals als Kandidaten fuer sichtbare Labels.
    tokens = re.findall(r'"([^"\n]+)"|\'([^\'\n]+)\'', line)
    flattened = [a or b for a, b in tokens]
    jsx_text = [segment.strip() for segment in re.findall(r">([^<{}][^<]*)<", raw_line)]
    return [
        token
        for token in [*flattened, *jsx_text]
        if token
        and not token.startswith("@/")
        and not token.startswith("./")
        and not token.startswith("../")
        and "/" not in token
    ]


def _collect_files(base: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("app/**/*.ts", "app/**/*.tsx", "components/**/*.ts", "components/**/*.tsx", "lib/**/*.ts", "lib/**/*.tsx", "messages/*.json"):
        files.extend(base.glob(pattern))
    return sorted(
        {
            p
            for p in files
            if p.is_file()
            and "__tests__" not in p.parts
            and ".test." not in p.name
            and ".spec." not in p.name
        }
    )


def analyze_german_ui(
    *,
    dashboard_src: Path,
    messages_dir: Path,
    policy_doc: Path,
    glossary_doc: Path,
) -> dict[str, Any]:
    issues: list[UiIssue] = []
    files_scanned = 0
    critical_hits = 0
    out_of_scope_hits = 0

    if not policy_doc.is_file():
        _issue(
            issues,
            severity="error",
            code="policy_missing",
            message=f"German-only UI policy missing: {policy_doc}",
        )

    policy_text = policy_doc.read_text(encoding="utf-8") if policy_doc.is_file() else ""

    if not glossary_doc.is_file() and "## 3) Verbindliches Glossar" not in policy_text:
        _issue(
            issues,
            severity="error",
            code="glossary_missing",
            message="Glossary missing and not embedded in policy.",
        )

    glossary_text = glossary_doc.read_text(encoding="utf-8") if glossary_doc.is_file() else ""
    combined_docs = f"{policy_text}\n{glossary_text}"
    missing_terms = [term for term in GERMAN_MAIN_CONSOLE_TERMS if term not in combined_docs]
    if missing_terms:
        _issue(
            issues,
            severity="error",
            code="missing_german_core_terms",
            message="Missing required German main-console terms: " + ", ".join(missing_terms),
        )

    if not dashboard_src.is_dir():
        _issue(
            issues,
            severity="error",
            code="dashboard_src_missing",
            message=f"Dashboard source missing: {dashboard_src}",
        )
        return {
            "ok": False,
            "files_scanned": 0,
            "critical_hits": 0,
            "out_of_scope_hits": 0,
            "message_files": [],
            "issues": [asdict(i) for i in issues],
            "error_count": len([i for i in issues if i.severity == "error"]),
            "warning_count": len([i for i in issues if i.severity == "warning"]),
        }

    if not messages_dir.is_dir():
        _issue(
            issues,
            severity="error",
            code="messages_dir_missing",
            message=f"Messages directory missing: {messages_dir}",
        )

    message_files = sorted([p.name for p in messages_dir.glob("*.json") if p.is_file()])
    if not message_files:
        _issue(
            issues,
            severity="error",
            code="message_files_missing",
            message="No message files found under dashboard messages directory.",
            path=str(messages_dir),
        )

    for file_path in _collect_files(dashboard_src):
        if file_path.name == "en.json":
            # English locale file is allowed as development fallback and is not the
            # target surface for Philipp.
            continue
        files_scanned += 1
        for idx, raw_line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("//") or line.startswith("/*") or line.startswith("*") or line.startswith("*/"):
                continue
            candidates = _extract_candidate_strings(file_path, raw_line)
            for token in candidates:
                if _looks_technical(token):
                    continue
                for phrase in CRITICAL_ENGLISH_VISIBLE_PHRASES:
                    if phrase in token:
                        critical_hits += 1
                        _issue(
                            issues,
                            severity="error",
                            code="critical_english_visible_label",
                            message=f"Critical English visible phrase detected: {phrase}",
                            path=str(file_path),
                            line=idx,
                        )
                for phrase in OUT_OF_SCOPE_VISIBLE_PHRASES:
                    if _skip_out_of_scope_scan(file_path):
                        continue
                    if _looks_like_intl_message_key(token):
                        continue
                    if phrase in token:
                        out_of_scope_hits += 1
                        _issue(
                            issues,
                            severity="warning",
                            code="out_of_scope_visible_phrase",
                            message=f"Out-of-scope visible phrase detected: {phrase}",
                            path=str(file_path),
                            line=idx,
                        )

    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "ok": not errors,
        "files_scanned": files_scanned,
        "critical_hits": critical_hits,
        "out_of_scope_hits": out_of_scope_hits,
        "message_files": message_files,
        "issues": [asdict(issue) for issue in issues],
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_german_only_ui: dashboard surface",
        f"ok={str(summary['ok']).lower()} files_scanned={summary['files_scanned']}",
        f"critical_hits={summary['critical_hits']} out_of_scope_hits={summary['out_of_scope_hits']}",
        "message_files=" + ", ".join(summary["message_files"]) if summary["message_files"] else "message_files=none",
    ]
    for issue in summary["issues"]:
        where = ""
        if issue.get("path"):
            where = f" [{issue['path']}"
            if issue.get("line"):
                where += f":{issue['line']}"
            where += "]"
        lines.append(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{where}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dashboard-src", type=Path, default=DASHBOARD_SRC_DEFAULT)
    parser.add_argument("--messages-dir", type=Path, default=MESSAGES_DIR_DEFAULT)
    parser.add_argument("--policy-doc", type=Path, default=POLICY_DOC_DEFAULT)
    parser.add_argument("--glossary-doc", type=Path, default=GLOSSARY_DOC_DEFAULT)
    args = parser.parse_args(argv)

    summary = analyze_german_ui(
        dashboard_src=args.dashboard_src,
        messages_dir=args.messages_dir,
        policy_doc=args.policy_doc,
        glossary_doc=args.glossary_doc,
    )

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_text(summary))

    if not args.strict:
        return 0
    if summary["error_count"] > 0:
        return 1
    if summary["critical_hits"] > 0 or summary["out_of_scope_hits"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
