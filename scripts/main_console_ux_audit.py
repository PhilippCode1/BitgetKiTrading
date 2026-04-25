#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP_CONSOLE_DIR = ROOT / "apps" / "dashboard" / "src" / "app" / "(operator)" / "console"
NAV_FILE = ROOT / "apps" / "dashboard" / "src" / "lib" / "main-console" / "navigation.ts"
DE_MESSAGES = ROOT / "apps" / "dashboard" / "src" / "messages" / "de.json"

FORBIDDEN_TERMS = ("billing", "customer", "pricing", "saas")
MAIN_AREAS = (
    "Übersicht",
    "Asset-Universum",
    "Charts & Markt",
    "Signale & Strategien",
    "Risk & Portfolio",
    "Live-Broker",
    "Sicherheitszentrale",
    "Incidents & Health",
    "Reports & Evidence",
    "Einstellungen",
)
ENGLISH_LABEL_HINTS = ("overview", "settings", "reports", "signals", "market")


def _discover_routes() -> list[str]:
    routes: list[str] = []
    if not APP_CONSOLE_DIR.is_dir():
        return routes
    for p in APP_CONSOLE_DIR.rglob("page.tsx"):
        rel = p.relative_to(APP_CONSOLE_DIR).as_posix()
        rel = rel.removesuffix("/page.tsx")
        rel = rel.removesuffix("page.tsx")
        route = "/console" if rel in {"", "."} else f"/console/{rel}"
        route = route.replace("//", "/")
        routes.append(route)
    return sorted(set(routes))


def _extract_nav_links() -> list[str]:
    if not NAV_FILE.is_file():
        return []
    text = NAV_FILE.read_text(encoding="utf-8")
    links: list[str] = []
    for m in re.finditer(r"href:\s*`([^`]+)`", text):
        links.append(m.group(1))
    for m in re.finditer(r'href:\s*"([^"]+)"', text):
        links.append(m.group(1))
    return sorted(set(links))


def _extract_de_labels_text() -> str:
    return DE_MESSAGES.read_text(encoding="utf-8") if DE_MESSAGES.is_file() else ""


def build_audit() -> dict[str, Any]:
    routes = _discover_routes()
    nav_links = _extract_nav_links()
    labels_text = _extract_de_labels_text()
    nav_text = NAV_FILE.read_text(encoding="utf-8") if NAV_FILE.is_file() else ""

    potentially_dead_routes: list[str] = [
        r for r in routes if (r != "/console" and r not in nav_links)
    ]
    billing_hits: list[str] = [r for r in routes if any(t in r.lower() for t in FORBIDDEN_TERMS)]
    english_label_hits: list[str] = []
    for token in ("overview", "health map", "safety center", "reports", "settings"):
        if token in labels_text.lower():
            english_label_hits.append(token)

    routes_without_main_console_mapping: list[str] = []
    for route in routes:
        short = route.replace("/console/", "").replace("/console", "")
        if short and short not in nav_text:
            routes_without_main_console_mapping.append(route)

    empty_state_guard_missing = []
    error_state_guard_missing = []
    for p in APP_CONSOLE_DIR.rglob("page.tsx"):
        txt = p.read_text(encoding="utf-8")
        if "EmptyStateHelp" not in txt and "empty" not in txt.lower():
            empty_state_guard_missing.append(str(p.relative_to(ROOT)))
        if "PanelDataIssue" not in txt and "error" not in txt.lower():
            error_state_guard_missing.append(str(p.relative_to(ROOT)))

    route_classification: dict[str, str] = {}
    for route in routes:
        low = route.lower()
        if any(t in low for t in FORBIDDEN_TERMS):
            route_classification[route] = "deprecated_internal"
        elif "/console/admin" in low:
            route_classification[route] = "intern_ops_only"
        elif route in nav_links or route == "/console":
            route_classification[route] = "behalten_main_console"
        else:
            route_classification[route] = "technisch_benoetigt_nicht_prominent"

    required_area_presence = {
        "Sicherheitszentrale": any("/console/safety-center" == r for r in routes),
        "Asset-Universum": any("/console/market-universe" == r for r in routes),
    }

    p0_blockers = []
    if "/console/safety-center" not in routes:
        p0_blockers.append("Sicherheitszentrale-Route fehlt")
    if "/console/market-universe" not in routes:
        p0_blockers.append("Asset-Universum-Route fehlt")
    if not NAV_FILE.is_file():
        p0_blockers.append("Main-Console-Navigation fehlt")

    return {
        "summary": {
            "route_count": len(routes),
            "nav_link_count": len(nav_links),
            "p0_blocker_count": len(p0_blockers),
        },
        "known_routes": routes,
        "navigation_links": nav_links,
        "potentially_dead_routes": potentially_dead_routes,
        "billing_customer_pricing_saas_hits": billing_hits,
        "english_main_label_hits": english_label_hits,
        "routes_without_main_console_mapping": routes_without_main_console_mapping,
        "route_classification": route_classification,
        "empty_state_guard_missing": empty_state_guard_missing,
        "error_state_guard_missing": error_state_guard_missing,
        "required_area_presence": required_area_presence,
        "required_main_areas_de": list(MAIN_AREAS),
        "p0_blockers": p0_blockers,
        "english_label_policy_hits": [
            token for token in ENGLISH_LABEL_HINTS if token in labels_text.lower()
        ],
    }


def to_markdown(payload: dict[str, Any]) -> str:
    s = payload["summary"]
    lines = [
        "# Main Console UX Audit",
        "",
        "## Zusammenfassung",
        f"- Routen gesamt: `{s['route_count']}`",
        f"- Navigationseinträge: `{s['nav_link_count']}`",
        f"- P0-UX-Blocker: `{s['p0_blocker_count']}`",
        "",
        "## Routeninventar",
    ]
    lines.extend(f"- `{r}`" for r in payload["known_routes"])
    lines.extend(["", "## Navigation & Labels", f"- Navigationseinträge: `{len(payload['navigation_links'])}`"])
    lines.extend(f"- `{r}`" for r in payload["navigation_links"])
    lines.extend(["", "## Tote oder unklare Seiten"])
    if payload["potentially_dead_routes"]:
        lines.extend(f"- `{r}`" for r in payload["potentially_dead_routes"])
    else:
        lines.append("- Keine potenziell toten Seiten erkannt.")
    lines.extend(["", "## Empty-State Pflicht"])
    if payload["empty_state_guard_missing"]:
        lines.extend(f"- `{p}`" for p in payload["empty_state_guard_missing"])
    else:
        lines.append("- Empty-State-Guard in allen geprüften Seiten erkennbar.")
    lines.extend(["", "## Error-State Pflicht"])
    if payload["error_state_guard_missing"]:
        lines.extend(f"- `{p}`" for p in payload["error_state_guard_missing"])
    else:
        lines.append("- Error-State-Guard in allen geprüften Seiten erkennbar.")
    lines.extend(["", "## Main-Console-Bereiche"])
    for name, present in payload["required_area_presence"].items():
        lines.append(f"- {name}: `{'vorhanden' if present else 'fehlt'}`")
    lines.extend(["", "## P0-UX-Blocker"])
    if payload["p0_blockers"]:
        lines.extend(f"- {b}" for b in payload["p0_blockers"])
    else:
        lines.append("- Keine P0-UX-Blocker erkannt.")
    lines.extend(["", "## Routenklassifikation"])
    for route, classification in sorted(payload["route_classification"].items()):
        lines.append(f"- `{route}` -> `{classification}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Main Console UX-Audit (Routen, Navigation, States).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-md")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_audit()
    if args.dry_run:
        print("main_console_ux_audit: dry-run=true")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"main_console_ux_audit: routes={payload['summary']['route_count']} "
            f"nav={payload['summary']['nav_link_count']} p0={payload['summary']['p0_blocker_count']}"
        )
    if args.output_md:
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
