#!/usr/bin/env python3
"""Static checks for German-only productive UI language."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DE_MESSAGES = ROOT / "apps" / "dashboard" / "src" / "messages" / "de.json"
NAV_FILE = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
STATUS_DOC = ROOT / "docs" / "production_10_10" / "german_ui_status_language.md"
OP_STATUS_DOC = ROOT / "docs" / "operator_status_language.md"

FORBIDDEN_NAV_TERMS = (
    "billing",
    "customer",
    "tenant",
    "pricing",
    "plans",
    "subscribe",
    "contract",
    "sales",
)
FORBIDDEN_PROMISES = (
    "gewinn garantiert",
    "garantierte gewinne",
    "sichere rendite",
    "risikofreie rendite",
    "profit guarantee",
    "guaranteed profit",
)
REQUIRED_DE_NAV_LABELS = (
    "Übersicht",
    "Asset-Universum",
    "Charts & Markt",
    "Signale & KI-Erklärung",
    "Risiko & Portfolio",
    "Paper/Shadow/Live-Freigabestatus",
    "Live-Broker & Ausführungssicherheit",
    "Systemstatus & Warnungen",
    "Berichte & Nachweise",
    "Einstellungen & Laufzeitprüfungen",
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _add(issues: list[Issue], severity: str, code: str, message: str, path: Path | None = None) -> None:
    issues.append(Issue(severity=severity, code=code, message=message, path=str(path) if path else None))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def analyze() -> dict[str, Any]:
    issues: list[Issue] = []

    for required in (DE_MESSAGES, NAV_FILE, STATUS_DOC, OP_STATUS_DOC):
        if not required.is_file():
            _add(issues, "error", "required_file_missing", f"Pflichtdatei fehlt: {required}", required)

    if DE_MESSAGES.is_file():
        try:
            payload = json.loads(_read(DE_MESSAGES))
        except Exception:
            payload = {}
            _add(issues, "error", "de_json_invalid", "de.json ist nicht parsebar.", DE_MESSAGES)
        nav_values = list((((payload.get("console") or {}).get("nav")) or {}).values())
        nav_values_text = "\n".join(str(v) for v in nav_values)
        for required in REQUIRED_DE_NAV_LABELS:
            if required not in nav_values_text:
                _add(issues, "error", "required_german_nav_label_missing", f"Pflichtlabel fehlt: {required}", DE_MESSAGES)
        for token in FORBIDDEN_NAV_TERMS:
            if re.search(rf"\b{re.escape(token)}\b", nav_values_text, flags=re.IGNORECASE):
                _add(issues, "error", "forbidden_term_in_visible_nav", f"Verbotener Begriff in sichtbarer Navigation: {token}", DE_MESSAGES)

    if NAV_FILE.is_file():
        nav_text = _read(NAV_FILE).lower()
        href_literals = re.findall(r'href:\s*"([^"]+)"', nav_text)
        for token in FORBIDDEN_NAV_TERMS:
            if any(token in href for href in href_literals):
                _add(issues, "error", "forbidden_route_in_primary_nav", f"Verbotener Hauptnavigationspfad gefunden: {token}", NAV_FILE)

    for scan_path in (DE_MESSAGES, OP_STATUS_DOC):
        if not scan_path.is_file():
            continue
        low = _read(scan_path).lower()
        for phrase in FORBIDDEN_PROMISES:
            if phrase in low:
                _add(issues, "error", "forbidden_profit_promise", f"Verbotenes Gewinnversprechen gefunden: {phrase}", scan_path)

    if STATUS_DOC.is_file():
        status_text = _read(STATUS_DOC).lower()
        required_status_topics = (
            "erlaubte statusbegriffe",
            "verbotene begriffe",
            "standardtexte fuer fehler",
            "standardtexte fuer leere zustaende",
            "standardtexte fuer live-blockaden",
            "standardtexte fuer asset-quarantaene",
            "standardtexte fuer paper/shadow/live",
        )
        for topic in required_status_topics:
            if topic not in status_text:
                _add(issues, "error", "status_doc_topic_missing", f"Statussprach-Doku unvollstaendig: {topic}", STATUS_DOC)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "ok": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "issues": [asdict(i) for i in issues],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = analyze()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "check_german_ui_language: ok="
            f"{str(summary['ok']).lower()} errors={summary['error_count']} warnings={summary['warning_count']}"
        )
        for issue in summary["issues"]:
            where = f" [{issue['path']}]" if issue.get("path") else ""
            print(f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{where}")

    if not args.strict:
        return 0
    return 1 if (summary["error_count"] > 0 or summary["warning_count"] > 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
