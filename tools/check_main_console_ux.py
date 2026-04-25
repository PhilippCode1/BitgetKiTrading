#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NAV_PATH = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
DE_MESSAGES_PATH = ROOT / "apps" / "dashboard" / "src" / "messages" / "de.json"
FORBIDDEN_NAV_TERMS = ("billing", "customer", "pricing", "contract", "saas", "tenant")
REQUIRED_NAV_KEYS = (
    "console.nav.overview",
    "console.nav.asset_universe",
    "console.nav.charts_market",
    "console.nav.signals_ai",
    "console.nav.risk_portfolio",
    "console.nav.readiness_modes",
    "console.nav.live_broker_safety",
    "console.nav.system_alerts",
    "console.nav.reports_evidence",
    "console.nav.settings_runtime",
)


def analyze() -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    required = (
        (ROOT / "docs" / "production_10_10" / "main_console_architecture.md", "architecture_doc_missing", "Main-Console-Architektur fehlt."),
        (ROOT / "docs" / "production_10_10" / "main_console_ux_finalization.md", "doc_missing", "UX-Finalisierungsdoku fehlt."),
        (ROOT / "scripts" / "main_console_ux_audit.py", "audit_script_missing", "UX-Audit-Script fehlt."),
        (ROOT / "tests" / "scripts" / "test_main_console_ux_audit.py", "audit_script_test_missing", "UX-Audit-Script-Test fehlt."),
        (ROOT / "tools" / "check_main_console_ux.py", "checker_missing", "UX-Checker fehlt."),
        (ROOT / "tests" / "tools" / "test_check_main_console_ux.py", "checker_test_missing", "UX-Checker-Test fehlt."),
        (ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts", "navigation_missing", "Zentrale Main-Console-Navigation fehlt."),
    )
    for p, code, msg in required:
        if not p.is_file():
            issues.append({"severity": "error", "code": code, "message": msg, "path": str(p)})

    doc = ROOT / "docs" / "production_10_10" / "main_console_ux_finalization.md"
    if doc.is_file():
        text = doc.read_text(encoding="utf-8").lower()
        for section in (
            "routeninventar",
            "navigation-bereinigung",
            "tote oder unklare seiten",
            "main-console-bereiche",
            "manuelle browser-pruefung",
        ):
            if section not in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "doc_section_missing",
                        "message": f"Pflichtabschnitt fehlt: {section}",
                        "path": str(doc),
                    }
                )
        for must in ("sicherheitszentrale", "asset-universum", "error-state", "empty-state"):
            if must not in text:
                issues.append(
                    {
                        "severity": "error",
                        "code": "doc_required_term_missing",
                        "message": f"Pflichtbegriff fehlt: {must}",
                        "path": str(doc),
                    }
                )

    if NAV_PATH.is_file():
        nav_text = NAV_PATH.read_text(encoding="utf-8")
        nav_text_lower = nav_text.lower()
        href_literals = re.findall(r'href:\s*"([^"]+)"', nav_text_lower)
        for term in FORBIDDEN_NAV_TERMS:
            if any(term in href for href in href_literals):
                issues.append(
                    {
                        "severity": "error",
                        "code": "forbidden_term_in_main_navigation",
                        "message": f"Verbotener Begriff in Main-Navigation: {term}",
                        "path": str(NAV_PATH),
                    }
                )
        for key in REQUIRED_NAV_KEYS:
            if key not in nav_text_lower:
                issues.append(
                    {
                        "severity": "error",
                        "code": "required_nav_module_missing",
                        "message": f"Pflichtmodul fehlt in Navigation: {key}",
                        "path": str(NAV_PATH),
                    }
                )

    if DE_MESSAGES_PATH.is_file():
        try:
            payload = json.loads(DE_MESSAGES_PATH.read_text(encoding="utf-8"))
            nav_obj = (((payload.get("console") or {}).get("nav")) or {})
            required_de_labels = (
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
            values = [str(v) for v in nav_obj.values()]
            for label in required_de_labels:
                if label not in values:
                    issues.append(
                        {
                            "severity": "error",
                            "code": "missing_german_nav_label",
                            "message": f"Deutsches Hauptlabel fehlt: {label}",
                            "path": str(DE_MESSAGES_PATH),
                        }
                    )
        except Exception:
            issues.append(
                {
                    "severity": "error",
                    "code": "de_messages_not_parseable",
                    "message": "de.json konnte nicht geparst werden.",
                    "path": str(DE_MESSAGES_PATH),
                }
            )

    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    return {"ok": len(errors) == 0, "error_count": len(errors), "warning_count": len(warnings), "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueft Main Console UX-Finalisierungsartefakte.")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = analyze()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"check_main_console_ux: ok={str(payload['ok']).lower()} "
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
