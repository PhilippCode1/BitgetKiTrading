#!/usr/bin/env python3
"""Check main-console route inventory and IA documentation."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "apps" / "dashboard" / "src" / "app"
IA_DOC_DEFAULT = (
    ROOT / "docs" / "production_10_10" / "main_console_information_architecture.md"
)

IRRELEVANT_TERMS = (
    "billing",
    "pricing",
    "customer",
    "tenant",
    "subscription",
    "checkout",
    "payment",
)

REQUIRED_GERMAN_NAV_LABELS = (
    "Übersicht",
    "Bitget Assets",
    "Signale & Strategien",
    "Risk & Portfolio",
    "Live-Broker",
    "Shadow & Evidence",
    "System Health",
    "Einstellungen",
    "Reports",
    "Admin/Owner",
)

REQUIRED_IA_SECTIONS = (
    "## Zentrale Navigation",
    "## Routen-Mapping",
    "## Konsolidierungsregeln",
)


@dataclass(frozen=True)
class RouteIssue:
    severity: str
    code: str
    message: str
    path: str | None = None


def _normalize_route(path: Path, marker: str) -> str:
    rel = path.as_posix().split(marker, 1)[1]
    rel = rel.rsplit("/", 1)[0]
    segments = [segment for segment in rel.split("/") if segment]
    cleaned = [segment for segment in segments if not segment.startswith("(")]
    if not cleaned:
        return "/"
    return "/" + "/".join(cleaned)


def discover_ui_routes(app_dir: Path) -> list[str]:
    routes: set[str] = set()
    for page in app_dir.rglob("page.tsx"):
        routes.add(_normalize_route(page, "/app/"))
    return sorted(routes)


def discover_api_routes(app_dir: Path) -> list[str]:
    routes: set[str] = set()
    for route_file in app_dir.rglob("route.ts"):
        route = _normalize_route(route_file, "/app/")
        routes.add(route)
    return sorted(routes)


def _extract_documented_routes(markdown: str) -> list[str]:
    return sorted(set(re.findall(r"`(/[^`\s]+)`", markdown)))


def _issue(
    issues: list[RouteIssue],
    *,
    severity: str,
    code: str,
    message: str,
    path: str | None = None,
) -> None:
    issues.append(
        RouteIssue(
            severity=severity,
            code=code,
            message=message,
            path=path,
        )
    )


def analyze_routes(app_dir: Path, ia_doc: Path) -> dict[str, Any]:
    issues: list[RouteIssue] = []
    ui_routes = discover_ui_routes(app_dir)
    api_routes = discover_api_routes(app_dir)

    if not ui_routes:
        _issue(
            issues,
            severity="error",
            code="no_ui_routes_found",
            message="No dashboard UI routes detected under apps/dashboard/src/app.",
        )

    irrelevant_hits: list[dict[str, str]] = []
    all_routes = ui_routes + api_routes
    for route in all_routes:
        lower = route.lower()
        for term in IRRELEVANT_TERMS:
            if term in lower:
                irrelevant_hits.append({"term": term, "route": route})
                _issue(
                    issues,
                    severity="warning",
                    code="irrelevant_term_detected",
                    message=f"Irrelevanter Begriff im Route-Pfad: {term}",
                    path=route,
                )
                break

    ia_text = ""
    if not ia_doc.is_file():
        _issue(
            issues,
            severity="error",
            code="ia_doc_missing",
            message=f"Main-Console-IA-Dokument fehlt: {ia_doc}",
        )
    else:
        ia_text = ia_doc.read_text(encoding="utf-8")
        for section in REQUIRED_IA_SECTIONS:
            if section not in ia_text:
                _issue(
                    issues,
                    severity="error",
                    code="ia_missing_section",
                    message=f"Fehlender IA-Abschnitt: {section}",
                    path=str(ia_doc),
                )

        missing_labels = [
            label for label in REQUIRED_GERMAN_NAV_LABELS if label not in ia_text
        ]
        if missing_labels:
            _issue(
                issues,
                severity="error",
                code="ia_missing_german_navigation",
                message="Fehlende deutsche Navigationslabels: "
                + ", ".join(missing_labels),
                path=str(ia_doc),
            )

        documented_routes = _extract_documented_routes(ia_text)
        if not documented_routes:
            _issue(
                issues,
                severity="error",
                code="ia_missing_documented_routes",
                message="IA-Dokument enthaelt keine dokumentierten Route-Hinweise (`/console/...`).",
                path=str(ia_doc),
            )
        else:
            existing = set(ui_routes + api_routes)
            for route in documented_routes:
                if route.startswith("/console") or route.startswith("/api/"):
                    if route not in existing:
                        _issue(
                            issues,
                            severity="warning",
                            code="ia_route_not_found",
                            message="Dokumentierter Navigationspfad existiert nicht als Route.",
                            path=route,
                        )

    summary = {
        "ui_route_count": len(ui_routes),
        "api_route_count": len(api_routes),
        "ui_routes": ui_routes,
        "api_routes": api_routes,
        "irrelevant_hits": irrelevant_hits,
        "issue_count": len(issues),
        "error_count": len([x for x in issues if x.severity == "error"]),
        "warning_count": len([x for x in issues if x.severity == "warning"]),
        "issues": [asdict(issue) for issue in issues],
    }
    return summary


def render_text(summary: dict[str, Any]) -> str:
    lines = [
        "check_main_console_routes: dashboard inventory",
        f"ui_routes={summary['ui_route_count']} api_routes={summary['api_route_count']}",
        f"errors={summary['error_count']} warnings={summary['warning_count']}",
    ]
    if summary["irrelevant_hits"]:
        lines.append(
            "irrelevant_terms="
            + ", ".join(
                f"{hit['term']}@{hit['route']}" for hit in summary["irrelevant_hits"][:20]
            )
        )
    for issue in summary["issues"]:
        suffix = f" [{issue['path']}]" if issue["path"] else ""
        lines.append(
            f"{issue['severity'].upper()} {issue['code']}: {issue['message']}{suffix}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--app-dir", type=Path, default=APP_DIR)
    parser.add_argument("--ia-doc", type=Path, default=IA_DOC_DEFAULT)
    args = parser.parse_args(argv)

    summary = analyze_routes(args.app_dir, args.ia_doc)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(render_text(summary))

    if summary["error_count"] > 0:
        return 1
    if args.strict and (
        summary["warning_count"] > 0
        or summary["ui_route_count"] == 0
        or summary["api_route_count"] == 0
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
