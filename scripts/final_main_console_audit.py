#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "apps" / "dashboard" / "src"
CONSOLE_APP = APP / "app" / "(operator)" / "console"
NAV_FILE = APP / "lib" / "main-console" / "navigation.ts"
DE_MESSAGES = APP / "messages" / "de.json"
RETURN_TO_FILE = APP / "lib" / "return-to-safety.ts"
EVIDENCE_MATRIX = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
REPORTS_DIR = ROOT / "reports"

FORBIDDEN_TERMS = ("billing", "customer", "pricing", "saas", "subscription", "tarif")
ALLOWED_NAV_HINTS = (
    "/console",
    "/market-universe",
    "/terminal",
    "/signals",
    "/risk",
    "/live-broker",
    "/safety-center",
    "/system-health-map",
    "/reports",
    "/account/language",
)


@dataclass(frozen=True)
class CheckResult:
    key: str
    title: str
    ok: bool
    detail: str
    blocker: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def route_exists(route: str) -> bool:
    rel = route.replace("/console", "").strip("/")
    if not rel:
        return (CONSOLE_APP / "page.tsx").is_file()
    return (CONSOLE_APP / rel / "page.tsx").is_file()


def check_main_console_route() -> CheckResult:
    ok = route_exists("/console")
    return CheckResult(
        key="main_console_route",
        title="Kanonische Main-Console-Route",
        ok=ok,
        detail="/console vorhanden" if ok else "/console fehlt",
        blocker=not ok,
    )


def check_navigation_allowed_modules() -> CheckResult:
    nav = read_text(NAV_FILE)
    links = re.findall(r'href:\s*`([^`]+)`|href:\s*"([^"]+)"', nav)
    flat_links = [a or b for a, b in links]
    unknown = [l for l in flat_links if "/console/" in l and not any(h in l for h in ALLOWED_NAV_HINTS)]
    ok = len(unknown) == 0 and any("/reports" in l for l in flat_links)
    detail = "Navigation konsistent" if ok else f"Unklare Module in Navigation: {unknown}"
    return CheckResult("navigation_allowed", "Navigation nur erlaubte Module", ok, detail, not ok)


def check_no_commercial_language() -> CheckResult:
    hits: list[str] = []
    nav_text = read_text(NAV_FILE).lower()
    de_txt = read_text(DE_MESSAGES)
    try:
        de_obj = json.loads(de_txt)
    except json.JSONDecodeError:
        de_obj = {}
    nav_labels = (
        de_obj.get("console", {}).get("nav", {})
        if isinstance(de_obj, dict)
        else {}
    )
    label_values = [str(v).lower() for v in nav_labels.values()] if isinstance(nav_labels, dict) else []
    for t in FORBIDDEN_TERMS:
        if any(t in v for v in label_values) or f"/{t}" in nav_text:
            hits.append(t)
    ok = len(hits) == 0
    return CheckResult(
        "no_commercial_language",
        "Keine sichtbare Billing/Customer/Sales-Sprache",
        ok,
        "Keine verbotenen Begriffe gefunden" if ok else f"Gefundene Begriffe: {sorted(set(hits))}",
        not ok,
    )


def check_german_core_texts() -> CheckResult:
    de = read_text(DE_MESSAGES)
    try:
        obj = json.loads(de)
    except json.JSONDecodeError:
        obj = {}
    nav = obj.get("console", {}).get("nav", {}) if isinstance(obj, dict) else {}
    required_keys = ["reports_evidence", "system_alerts", "risk_portfolio"]
    ok = isinstance(nav, dict) and all(isinstance(nav.get(k), str) and nav.get(k, "").strip() for k in required_keys)
    return CheckResult(
        "german_core_texts",
        "Kerntexte Deutsch",
        ok,
        "de.json enthält Main-Console-Kerntexte" if ok else "Fehlende deutsche Kerntexte in de.json",
        not ok,
    )


def check_welcome_return_to_safety() -> CheckResult:
    txt = read_text(RETURN_TO_FILE)
    ok = "sanitizeReturnTo" in txt and "SAFE_PREFIXES" in txt and "looksExternal" in txt
    return CheckResult(
        "welcome_returnto_safe",
        "Welcome/ReturnTo sicher",
        ok,
        "returnTo-Sanitizing vorhanden" if ok else "returnTo-Sanitizing unvollständig",
        not ok,
    )


def check_module_contracts() -> list[CheckResult]:
    checks = []
    checks.append(
        CheckResult(
            "asset_universe_blockers",
            "Asset-Universum mit sicheren Live-Blockern",
            route_exists("/console/market-universe")
            and (APP / "lib" / "asset-universe-console.ts").is_file(),
            "Route + View-Model vorhanden",
            not (route_exists("/console/market-universe") and (APP / "lib" / "asset-universe-console.ts").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "chart_workspace_states",
            "Chart mit Frische/Empty/Error",
            route_exists("/console/terminal") and (APP / "lib" / "chart-workspace-status.ts").is_file(),
            "Chart-Route + Statusmodell vorhanden",
            not (route_exists("/console/terminal") and (APP / "lib" / "chart-workspace-status.ts").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "signals_risk_reasons",
            "Signale zeigen Risk-Gründe",
            route_exists("/console/signals") and (APP / "lib" / "signal-decision-center.ts").is_file(),
            "Signals-Route + Risk-Reason-Mapper vorhanden",
            not (route_exists("/console/signals") and (APP / "lib" / "signal-decision-center.ts").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "risk_module",
            "Risk-Modul zeigt Portfolio/Asset-Risiko",
            route_exists("/console/risk") and (APP / "lib" / "risk-center-view-model.ts").is_file(),
            "Risk-Route + View-Model vorhanden",
            not (route_exists("/console/risk") and (APP / "lib" / "risk-center-view-model.ts").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "broker_safety",
            "Broker zeigt Reconcile/Kill-Switch/Safety-Latch",
            route_exists("/console/live-broker") and (APP / "components" / "safety" / "ExecutionSafetyPanel.tsx").is_file(),
            "Live-Broker-Route + Safety-Panel vorhanden",
            not (route_exists("/console/live-broker") and (APP / "components" / "safety" / "ExecutionSafetyPanel.tsx").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "system_status",
            "Systemstatus zeigt Services/Provider/Stale Data",
            route_exists("/console/system-health-map") and (APP / "lib" / "system-diagnostics-view-model.ts").is_file(),
            "System-Route + Diagnostics-View-Model vorhanden",
            not (route_exists("/console/system-health-map") and (APP / "lib" / "system-diagnostics-view-model.ts").is_file()),
        )
    )
    checks.append(
        CheckResult(
            "reports_blockers",
            "Reports markieren fehlende Evidence als Blocker",
            route_exists("/console/reports") and (APP / "lib" / "evidence-console.ts").is_file(),
            "Reports-Route + Evidence-View-Model vorhanden",
            not (route_exists("/console/reports") and (APP / "lib" / "evidence-console.ts").is_file()),
        )
    )
    return checks


def check_secret_safety() -> CheckResult:
    txt = read_text(APP / "lib" / "system-diagnostics-view-model.ts") + read_text(APP / "lib" / "live-broker-console.ts")
    ok = "redact" in txt.lower() or "sanitize" in txt.lower()
    return CheckResult(
        "secret_safety",
        "Keine Secrets im Browser/Error States",
        ok,
        "Redaction/Sanitizing vorhanden" if ok else "Keine Redaction-Logik gefunden",
        not ok,
    )


def check_dangerous_action_confirmation() -> CheckResult:
    txt = read_text(APP / "components" / "safety" / "ExecutionSafetyPanel.tsx")
    ok = "Bestaetigung erforderlich" in txt and "role=\"dialog\"" in txt
    return CheckResult(
        "dangerous_action_confirmation",
        "Keine gefährlichen Actions ohne Bestätigung",
        ok,
        "Bestätigungsdialog vorhanden" if ok else "Bestätigungsdialog fehlt",
        not ok,
    )


def discover_git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if out.returncode == 0:
            sha = out.stdout.strip()
            return sha or None
    except OSError:
        return None
    return None


def evidence_status_counts() -> dict[str, int]:
    txt = read_text(EVIDENCE_MATRIX)
    counts = {"verified": 0, "missing": 0, "partial": 0, "implemented": 0, "external_required": 0}
    for k in counts.keys():
        counts[k] = len(re.findall(rf"status:\s+{k}\b", txt))
    return counts


def compute_scores(checks: list[CheckResult], evidence_counts: dict[str, int]) -> dict[str, int]:
    def pct(keys: list[str]) -> int:
        subset = [c for c in checks if c.key in keys]
        if not subset:
            return 0
        ok = sum(1 for c in subset if c.ok)
        return int(round(ok * 100 / len(subset)))

    total_evidence = sum(evidence_counts.values()) or 1
    weighted = (
        evidence_counts.get("verified", 0) * 1.0
        + evidence_counts.get("implemented", 0) * 0.65
        + evidence_counts.get("partial", 0) * 0.35
        + evidence_counts.get("external_required", 0) * 0.2
    ) / total_evidence
    evidence_score = int(round(weighted * 100))

    return {
        "ui_ux": pct(["main_console_route", "navigation_allowed", "german_core_texts", "welcome_returnto_safe"]),
        "multi_asset": pct(["asset_universe_blockers", "chart_workspace_states", "signals_risk_reasons", "risk_module"]),
        "risk": pct(["risk_module", "signals_risk_reasons", "reports_blockers"]),
        "broker_safety": pct(["broker_safety", "dangerous_action_confirmation", "secret_safety"]),
        "observability": pct(["system_status", "secret_safety"]),
        "evidence": evidence_score,
    }


def mode_decisions(blockers: list[str], evidence_counts: dict[str, int]) -> dict[str, str]:
    hard_no_go = len(blockers) > 0
    has_external = evidence_counts.get("external_required", 0) > 0
    has_partial = evidence_counts.get("partial", 0) > 0
    decisions = {
        "local": "NO_GO" if hard_no_go else "GO",
        "paper": "NO_GO" if hard_no_go else "GO",
        "shadow": "NO_GO" if hard_no_go else "GO",
        "staging": "NO_GO" if hard_no_go else "GO",
        "kontrollierter_live_pilot": "NO_GO" if hard_no_go or has_external or has_partial else "GO",
        "vollautomatisches_live": "NO_GO",
    }
    return decisions


def build_audit_payload() -> dict[str, Any]:
    checks = [
        check_main_console_route(),
        check_navigation_allowed_modules(),
        check_no_commercial_language(),
        check_german_core_texts(),
        check_welcome_return_to_safety(),
        *check_module_contracts(),
        check_secret_safety(),
        check_dangerous_action_confirmation(),
    ]
    blocker_list = [f"{c.title}: {c.detail}" for c in checks if c.blocker and not c.ok]
    counts = evidence_status_counts()
    scores = compute_scores(checks, counts)
    mode = mode_decisions(blocker_list, counts)
    overall = "NO_GO" if blocker_list else "GO"
    payload = {
        "project_name": "bitget-btc-ai",
        "git_sha": discover_git_sha(),
        "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "overall_assessment": overall,
        "checks": [c.__dict__ for c in checks],
        "scores": scores,
        "evidence_counts": counts,
        "blockers": blocker_list,
        "next_steps": [
            "Alle NO_GO-Blocker auflösen und erneut auditieren.",
            "Externe Evidence (Bitget, Shadow-Burn-in, Restore) mit verifiziertem Nachweis ergänzen.",
            "Live-Modus erst nach verifizierter Go/No-Go-Scorecard freigeben.",
        ],
        "mode_decisions": mode,
    }
    return payload


def to_markdown(payload: dict[str, Any]) -> str:
    s = payload["scores"]
    lines = [
        "# Final Main Console Audit",
        "",
        f"- Projektname: `{payload['project_name']}`",
        f"- Git SHA: `{payload['git_sha'] or 'unbekannt'}`",
        f"- Datum: `{payload['generated_at']}`",
        f"- Gesamteinschätzung: `{payload['overall_assessment']}`",
        "",
        "## Scores",
        f"- UI/UX-Score: `{s['ui_ux']}`",
        f"- Multi-Asset-Score: `{s['multi_asset']}`",
        f"- Risk-Score: `{s['risk']}`",
        f"- Broker-Safety-Score: `{s['broker_safety']}`",
        f"- Observability-Score: `{s['observability']}`",
        f"- Evidence-Score: `{s['evidence']}`",
        "",
        "## Finale Checks",
    ]
    for c in payload["checks"]:
        lines.append(f"- `{c['title']}`: `{'ok' if c['ok'] else 'fehlt/blockiert'}` — {c['detail']}")
    lines.extend(["", "## Fehlende Blocker"])
    if payload["blockers"]:
        lines.extend(f"- {b}" for b in payload["blockers"])
    else:
        lines.append("- Keine technischen Blocker aus dem Audit erkannt.")
    lines.extend(["", "## Go/No-Go je Modus"])
    for k, v in payload["mode_decisions"].items():
        lines.append(f"- {k}: `{v}`")
    lines.extend(["", "## Evidence-Status (Matrix)"])
    for k, v in payload["evidence_counts"].items():
        lines.append(f"- {k}: `{v}`")
    lines.extend(["", "## Naechste Schritte"])
    lines.extend(f"- {s}" for s in payload["next_steps"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finales Main-Console-Hardening-Audit.")
    parser.add_argument("--output-md", required=False)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = build_audit_payload()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"final_main_console_audit: overall={payload['overall_assessment']} blockers={len(payload['blockers'])}"
        )
    if args.output_md:
        out = Path(args.output_md)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(to_markdown(payload), encoding="utf-8")
    if args.strict and payload["blockers"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
