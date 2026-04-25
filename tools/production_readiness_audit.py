#!/usr/bin/env python3
"""
Produktions-Readiness-Audit: trennt Evidenz-Level (L0–L5) und bewusst
externe Blocker. Kein willkuerliches PASS: 'ok_strict' nur, wenn L_min erfuellt.

--strict: Exit-Code 1, sobald der konfigurierte Fuer-Echtgeld-Mindestdruck
(einschliesslich L4/L5 wo gefordert) in einer Nicht-External-Kategorie fehlt.
GitHub Branch-Protection ist in einem Klon unsichtbar — separate Zeile,
zaehlt nicht gegen strict (BLOCKED_EXTERNAL).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Final

_DEFAULT_REPO = Path(__file__).resolve().parents[1]
CI_WORKFLOW: Final[Path] = Path(".github/workflows/ci.yml")
RELEASE_EVID_DIR: Final[Path] = Path("docs/release_evidence")


@dataclass(frozen=True)
class CategoryResult:
    id: str
    label_de: str
    level: int
    strict_min: int
    ok_strict: bool
    traffic: str  # GREEN|YELLOW|RED|BLOCKED_EXTERNAL
    details: str
    external: bool


def _read_text(p: Path, root: Path) -> str:
    f = root / p
    if not f.is_file():
        return ""
    return f.read_text(encoding="utf-8", errors="replace")


def _ci_yaml(root: Path) -> str:
    return _read_text(CI_WORKFLOW, root)


def _release_evidence_files(root: Path) -> list[Path]:
    d = root / RELEASE_EVID_DIR
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("**/*.md") if p.is_file())


def _l4_l5_by_marker(root: Path) -> dict[str, int]:
    """
    L4/L5, wenn in docs/release_evidence ein Marker steht, z. B.:
    readiness_mark: L4  category=disaster_recovery
    (Keine fiktiven Standarddateien; Prompts tragen reale Beweise ein.)
    """
    by_cat: dict[str, int] = {}
    for path in _release_evidence_files(root):
        t = path.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(
            r"readiness_mark:\s*L(4|5)\s+category=([a-z0-9_]+)",
            t,
            re.I,
        ):
            lvl, cid = int(m.group(1)), m.group(2).lower()
            by_cat[cid] = max(by_cat.get(cid, 0), lvl)
    return by_cat


def _apply_marks(
    level: int, detail: str, marks: dict[str, int], cid: str
) -> tuple[int, str]:
    m = marks.get(cid, 0)
    if m > int(level):
        return m, f"readiness_mark in {RELEASE_EVID_DIR} hebt Kategorie an (L{m})."
    return level, detail


def _level_ci(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("ci_branch", 0)
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} fuer ci_branch (L{m})."
    y = _ci_yaml(root)
    if not y:
        return 0, f"Fehlt {CI_WORKFLOW}."
    ok_gate = "check_release_approval_gates" in y or "release-approval-gate" in y
    ok_py = "pytest" in y
    if ok_gate and ok_py:
        return 3, f"{CI_WORKFLOW} enthaelt Merge-/Release-Gate-Referenz und pytest (L3)."
    if y:
        return 1, f"{CI_WORKFLOW} existiert, aber unklare L3-Abdeckung (Gate+pytest) (L1)."
    return 0, "Kein CI-Workflow sichtbar."


def _level_disaster(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = max(marks.get("disaster_recovery", 0), marks.get("dr", 0))
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} fuer disaster_recovery (L{m})."
    t = _read_text(Path("docs/migrations.md"), root) + _read_text(
        Path("docs/db-schema.md"), root
    )
    if re.search(r"restor|back.?up|pitr|snapshot|fail.?over|disaster|recovery", t, re.I):
        return 2, "Doku-Drift/Schema/Migrations nennen DR-Themen, kein L4-Report (L2)."
    if t.strip():
        return 1, "Doku-Datei(en) teilweise vorhanden, DR-Keywords schwach (L1)."
    return 0, "Kein DR-relevanter Nachweis sichtbar (L0)."


def _level_shadow(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = max(marks.get("shadow_burn_in", 0), marks.get("shadow", 0))
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} fuer shadow (L{m})."
    ramp = _read_text(Path("docs/shadow_burn_in_ramp.md"), root)
    script = (root / "scripts" / "verify_shadow_burn_in.py").is_file()
    if ramp and script:
        return 2, "shadow_burn_in_ramp + verify_shadow_burn_in.py (L2)."
    if ramp or script:
        return 1, "Nur Doku ODER nur Skript (L1)."
    return 0, "Shadow-Burn-in nicht ausreichend im Repo sichtbar (L0)."


def _level_alert(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("alert_routing", 0)
    if m >= 4:
        return m, f"readiness_mark (L{m})."
    tests = list((root / "tests").rglob("*.py")) if (root / "tests").is_dir() else []
    hits = [p for p in tests if "alert" in str(p) or "monitor" in str(p)]
    ciy = _ci_yaml(root)
    if hits and "pytest" in ciy:
        return 3, "Tests unter tests/ (alert/monitor) + CI/pytest (L3)."
    if hits:
        return 2, "Unit-Tests zu Alert/Monitor, CI nicht verifiziert (L2)."
    if (root / "services" / "alert-engine").is_dir() and (
        root / "services" / "monitor-engine"
    ).is_dir():
        return 1, "Service-Verzeichnisse, duenne Test-Trace (L1)."
    return 0, "Kein Test-/CI-Trace fuer Alerting (L0)."


def _level_security(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = max(marks.get("security_audit", 0), marks.get("security", 0))
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} (L{m}) - ersetzt kein externes Audit-Programm."
    ciy = _ci_yaml(root)
    l3 = (
        "pip_audit_supply_chain_gate" in ciy
        and "check_production_env_template_security" in ciy
        and "pytest" in ciy
    )
    if l3:
        return 3, "CI: pip-audit-Gate, Prod-Template-Sicherheit, pytest (L3)."
    if "pip_audit" in ciy or "ruff" in ciy:
        return 2, "Teilweise Sicherheits-Tooling in CI (L2)."
    return 0, "Sicherheits-Tooling/CI-Trace Luecke (L0)."


def _level_customer_ui(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("customer_ui", 0)
    if m >= 4:
        return m, f"Staging-EV in {RELEASE_EVID_DIR} (L{m})."
    dash = (root / "apps" / "dashboard").is_dir()
    ciy = _ci_yaml(root)
    e2e = "e2e" in ciy or "playwright" in ciy
    if dash and e2e and "pnpm" in ciy:
        return 3, "apps/dashboard + E2E/Playwright in CI (L3)."
    if dash:
        return 2, "Dashboard, E2E-Referenz in CI unklar (L2)."
    return 0, "Kein Kunden-UI-Stack sichtbar (L0)."


def _level_secrets(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = max(marks.get("secrets_vault", 0), marks.get("secrets", 0))
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} (L{m}); Vault-Ops aussen bleibt extern."
    ciy = _ci_yaml(root)
    has_val = (root / "tools" / "validate_env_profile.py").is_file()
    has_chk = (root / "tools" / "check_production_env_template_security.py").is_file()
    l3 = has_val and has_chk and "check_production_env_template_security" in ciy
    if l3:
        return 3, "validate_env + Prod-Template-Gate in CI (L3)."
    if has_val and has_chk:
        return 2, "Gates vorhanden, CI-Referenz schwach (L2)."
    return 0, "Secrets-Policy-Tooling fehlt (L0)."


def _level_live_mirror(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("live_mirror", 0)
    if m >= 4:
        return m, f"readiness_mark (L{m})."
    ch = _read_text(Path("docs/LaunchChecklist.md"), root)
    lb = (root / "services" / "live-broker").is_dir()
    has_gate = re.search(
        r"LIVE_REQUIRE|REQUIRE_SHADOW|LIVE_.*GATE|manual",
        ch,
        re.I,
    )
    tlive2 = any((root / "tests").rglob("*live_broker*")) or any(
        (root / "tests").rglob("*run85*")
    )
    if lb and (has_gate or ch) and tlive2:
        return 3, "Live-Broker + Checklist + Test-Referenzen (L3); Staging-Probe = L4 extern erwartbar."
    if lb and ch:
        return 2, "Doku + live-broker, Test-Trace duenn (L2)."
    if lb:
        return 1, "Nur Code (L1)."
    return 0, "Kein klarer Live-Mirror-Stack sichtbar (L0)."


def _level_performance(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("performance_alpha", 0)
    if m >= 4:
        return m, f"readiness_mark (L{m})."
    ciy = _ci_yaml(root)
    if "check_coverage" in ciy or "check_coverage_gates" in ciy or "modul_mate" in ciy:
        return 3, "Coverage-/Modul-Qualitaet in CI-Trace (L3) - keine Markt-Alpha-Garantie (L4)."
    if (root / "tools" / "check_coverage_gates.py").is_file():
        return 2, "Coverage-Tool, CI-Referenz schwach (L2)."
    return 0, "Wenig Performance/SLO-Trace sichtbar (L0)."


def _level_compliance(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("compliance", 0)
    if m >= 5:
        return m, f"readiness_mark L5 in {RELEASE_EVID_DIR} (L{m}) - ersetzt keine reale Rechtspruefung."
    ext = _read_text(Path("docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md"), root)
    if ext and len(ext) > 200:
        return 1, "EXTERNAL_GO_LIVE: Abhaengigkeiten benannt (L1), L5-Signoff fehlt im Repo-EV."
    return 0, "Recht/Compliance in Repo unzureichend adressiert (L0)."


def _level_release(root: Path, marks: dict[str, int]) -> tuple[int, str]:
    m = marks.get("release_evidence", 0)
    if m >= 4:
        return m, f"readiness_mark in {RELEASE_EVID_DIR} (L{m})."
    has_dir = (root / RELEASE_EVID_DIR).is_dir()
    has_tool = (
        (root / "tools" / "check_release_approval_gates.py").is_file()
        or (root / "tools" / "collect_release_evidence.ps1").is_file()
    )
    ciy = "check_release_approval_gates" in _ci_yaml(root)
    if has_dir and has_tool and ciy:
        return 3, f"{RELEASE_EVID_DIR} + Gate-Tool + CI-Referenz (L3)."
    if has_tool and ciy:
        return 2, "Gate+CI, release_evidence-Ordner Luecke (L2)."
    return 0, "Release-Trace Luecke (L0)."


def _branch_row() -> CategoryResult:
    return CategoryResult(
        id="github_branch_protection",
        label_de="GitHub Branch-Protection (Org, nicht klonpruefbar)",
        level=0,
        strict_min=0,
        ok_strict=True,
        traffic="BLOCKED_EXTERNAL",
        details=(
            "Nicht aus Git-Clone sichtbar; in GitHub UI/Org: "
            "'release-approval-gate' als required Status (s. ci.yml Kommentar). "
            "Evidenz: Org-Audit, kein Repo-Commit-Claim."
        ),
        external=True,
    )


def _build_categories(root: Path, marks: dict[str, int]) -> list[CategoryResult]:
    spec: list[tuple[str, str, int, Callable[[Path, dict[str, int]], tuple[int, str]]]] = [
        ("ci_branch", "CI/Workflow & Merge-Release-Gates (Definition im Repo)", 3, _level_ci),
        (
            "disaster_recovery",
            "Disaster Recovery (Backup/Restore-Realitaet)",
            4,
            _level_disaster,
        ),
        ("shadow_burn_in", "Shadow / Burn-in Strecke", 4, _level_shadow),
        ("alert_routing", "Alert-Routing (Monitor/Outbox/Operator)", 3, _level_alert),
        (
            "security_audit",
            "Sicherheitspruefung (Supply-Tooling vs. ext. Audit)",
            4,
            _level_security,
        ),
        ("customer_ui", "Kunden-UI (Dashboard) + E2E", 3, _level_customer_ui),
        (
            "secrets_vault",
            "Secrets, ENV-Validierung, Vault-Realitaet (Repo-Anteil)",
            4,
            _level_secrets,
        ),
        (
            "live_mirror",
            "Live-Mirror / Manual-Ramp-Gates (technisch im Repo)",
            3,
            _level_live_mirror,
        ),
        (
            "performance_alpha",
            "Performance / Qualitaet / SLO-Gates (keine Markt-Alpha-Garantie)",
            3,
            _level_performance,
        ),
        ("compliance", "Compliance / Recht (signierte Evidenz)", 5, _level_compliance),
        (
            "release_evidence",
            "Release- und Evidenz-Artefakte",
            3,
            _level_release,
        ),
    ]
    out: list[CategoryResult] = []
    for cid, label, smin, fn in spec:
        lvl, det = fn(root, marks)
        lvl, det = _apply_marks(lvl, det, marks, cid)
        out.append(
            CategoryResult(
                id=cid,
                label_de=label,
                level=int(lvl),
                strict_min=smin,
                ok_strict=bool(lvl >= smin),
                traffic="YELLOW",  # Platzhalter
                details=det,
                external=False,
            )
        )
    out.insert(1, _branch_row())
    return out


def _apply_strict_mutable(
    results: list[CategoryResult], strict: bool
) -> tuple[list[CategoryResult], bool]:
    """Setzt ok_strict+traffic+strict_ok. External-Zeile zaehlt nicht gegen strict_ok."""
    strict_ok = True
    out: list[CategoryResult] = []
    for c in results:
        if c.external:
            out.append(
                replace(
                    c,
                    ok_strict=True,
                )
            )
            continue
        s_ok = c.level >= c.strict_min
        if not s_ok:
            strict_ok = False
        if not strict:
            if c.level == 0:
                t = "RED"
            elif c.level < c.strict_min:
                t = "YELLOW"  # z. B. L3-Tooling, aber L4 fuer Echtgeld-EV verlangt
            elif c.level >= 3:
                t = "GREEN"
            else:
                t = "YELLOW"
            out.append(replace(c, ok_strict=s_ok, traffic=t))
            continue
        t = "RED" if not s_ok else "GREEN" if c.level >= 3 else "YELLOW"
        out.append(replace(c, ok_strict=s_ok, traffic=t))
    return out, strict_ok


def _global_traffic(
    strict: bool, strict_ok: bool, res: list[CategoryResult]
) -> str:
    if strict and not strict_ok:
        return "RED"
    nonex = [c for c in res if not c.external]
    if any(c.traffic == "RED" for c in nonex):
        return "RED"
    if any(c.traffic == "YELLOW" for c in nonex) or any(
        c.traffic == "BLOCKED_EXTERNAL" for c in res
    ):
        return "YELLOW"
    return "GREEN"


def run_audit(root: Path, strict: bool) -> dict[str, Any]:
    schema = root / "docs" / "production_10_10" / "readiness_evidence_schema.json"
    if not schema.is_file():
        return {
            "ok": False,
            "error": f"Fehlendes Schema: {schema}",
        }
    marks = _l4_l5_by_marker(root)
    built = _build_categories(root, marks)
    res, strict_ok = _apply_strict_mutable(built, strict)
    g = _global_traffic(strict, strict_ok, res)
    return {
        "ok": True,
        "schema_path": str(schema),
        "repo_root": str(root.resolve()),
        "strict": strict,
        "strict_ok": strict_ok,
        "ampel_global": g,
        "readiness_marks": marks,
        "categories": [asdict(x) for x in res],
    }


def _render_md(d: dict[str, Any]) -> str:
    if not d.get("ok", False):
        return f"# production_readiness_audit – Fehler\n\n{d.get('error', 'unknown')}\n"
    lines: list[str] = [
        "# Production-Readiness-Audit",
        "",
        f"**repo:** `{d.get('repo_root', '')}`  ",
        f"**Modus strict:** {d.get('strict', False)}  ",
        f"**strict_ok:** {d.get('strict_ok', False)}  ",
        f"**Ampel global:** {d.get('ampel_global', '')}  ",
        f"**Schema:** `{d.get('schema_path', '')}`",
        "",
        "| Kategorie | Ampel | L | L_min (Strict) | ok_strict | Details |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in d.get("categories", []):
        lines.append(
            f"| {c.get('label_de', c.get('id', ''))} | {c.get('traffic', '')} | {c.get('level', 0)} | {c.get('strict_min', 0)} | {c.get('ok_strict', False)} | {c.get('details', '')} |"
        )
    lines.extend(
        [
            "",
            "*BLOCKED_EXTERNAL:* Branch-Policy nicht klonpruefbar. ",
            "Kein fiktives Go-Live aus dieser Zeile ableiten. ",
            "",
            "**Hinweis:** `strict_ok: false` ist **erwartbar** ohne L4/L5-Datei-Nachweise. ",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Evidenzbasiertes Readiness-Audit (L0–L5), ohne Fake-Prod-Green."
    )
    ap.add_argument(
        "--repo-root",
        type=Path,
        default=_DEFAULT_REPO,
        help="Monorepo-Wurzel (Tests)",
    )
    ap.add_argument(
        "--strict", action="store_true", help="Exit-1 wenn Echtgeld-EV-Luecke"
    )
    ap.add_argument(
        "--summary-json", action="store_true", help="JSON auf stdout (maschinenlesbar)"
    )
    ap.add_argument(
        "--report-md", type=Path, default=None, help="Markdown-Report-Datei"
    )
    ap.add_argument(
        "--out-json", type=Path, default=None, help="JSON-Report-Datei"
    )
    args = ap.parse_args()
    d = run_audit(args.repo_root, args.strict)
    if d.get("ok") is not True:
        print(d.get("error", "Fehler"), file=sys.stderr)
        return 2
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.summary_json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(_render_md(d), encoding="utf-8")
    if not args.summary_json and not args.report_md and not args.out_json:
        print(_render_md(d))
    if args.strict and d.get("strict_ok") is False:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
