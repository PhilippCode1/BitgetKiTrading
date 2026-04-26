#!/usr/bin/env python3
"""Generate the Cursor master status for repeated 10/10 readiness runs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from scripts.production_readiness_scorecard import build_from_repo  # noqa: E402
from shared_py.readiness_scorecard import CategoryScore, ReadinessScorecard  # noqa: E402

DEFAULT_OUTPUT = ROOT / "docs" / "production_10_10" / "CURSOR_MASTER_STATUS.md"


@dataclass(frozen=True)
class AssessmentArea:
    number: int
    title: str
    category_ids: tuple[str, ...]


ASSESSMENT_AREAS: tuple[AssessmentArea, ...] = (
    AssessmentArea(1, "Produktziel und Scope-Klarheit", ("private_owner_scope",)),
    AssessmentArea(2, "Systemarchitektur", ("deployment_parity", "main_console_information_architecture")),
    AssessmentArea(3, "Service-Grenzen und Datenfluesse", ("deployment_parity", "audit_forensics")),
    AssessmentArea(4, "Trading-Kern / Signal-Engine", ("strategy_validation_per_asset_class",)),
    AssessmentArea(5, "Risk-Governance", ("portfolio_risk", "asset_risk_tiers")),
    AssessmentArea(6, "Portfolio-Risk", ("portfolio_risk",)),
    AssessmentArea(7, "Asset-Risk-Tiers", ("asset_risk_tiers",)),
    AssessmentArea(8, "Multi-Asset-Order-Sizing", ("multi_asset_order_sizing", "asset_risk_tiers")),
    AssessmentArea(9, "Instrumentenkatalog / Bitget Asset Universe", ("instrument_catalog", "bitget_asset_universe")),
    AssessmentArea(10, "Market-Data-Qualitaet pro Asset", ("market_data_quality_per_asset",)),
    AssessmentArea(11, "Liquiditaet / Spread / Slippage", ("liquidity_spread_slippage_per_asset",)),
    AssessmentArea(12, "Paper-Broker", ("strategy_validation_per_asset_class", "deployment_parity")),
    AssessmentArea(13, "Shadow-Modus", ("shadow_burn_in",)),
    AssessmentArea(14, "Live-Broker", ("live_broker_fail_closed",)),
    AssessmentArea(15, "Live-Broker Fail-Closed", ("live_broker_fail_closed",)),
    AssessmentArea(16, "Order-Idempotency", ("order_idempotency",)),
    AssessmentArea(17, "Reconcile-Safety", ("reconcile_safety",)),
    AssessmentArea(18, "Kill-Switch / Safety-Latch", ("kill_switch_safety_latch",)),
    AssessmentArea(19, "Emergency-Flatten", ("emergency_flatten",)),
    AssessmentArea(20, "Exchange-Readiness Bitget", ("bitget_exchange_readiness",)),
    AssessmentArea(21, "ENV-Profile", ("env_secrets_profiles", "deployment_parity")),
    AssessmentArea(22, "Secrets / Vault / Rotation", ("env_secrets_profiles", "supply_chain_security")),
    AssessmentArea(23, "API-Gateway Security", ("admin_access_single_owner", "frontend_main_console_security")),
    AssessmentArea(24, "Interne Service-Auth", ("admin_access_single_owner",)),
    AssessmentArea(25, "Dashboard / Main Console", ("main_console_information_architecture", "frontend_main_console_security")),
    AssessmentArea(26, "Deutsche UX / Operator-Sprache", ("german_only_ui",)),
    AssessmentArea(27, "Operator-Approval", ("final_go_no_go_scorecard", "admin_access_single_owner")),
    AssessmentArea(28, "Audit / Forensics / Replay", ("audit_forensics",)),
    AssessmentArea(29, "Observability / Metrics / Logs", ("observability_slos",)),
    AssessmentArea(30, "Alert-Routing / Incident-Drill", ("alert_routing",)),
    AssessmentArea(31, "Backup / Restore", ("backup_restore",)),
    AssessmentArea(32, "Disaster-Recovery", ("disaster_recovery", "backup_restore")),
    AssessmentArea(33, "CI/CD", ("deployment_parity", "supply_chain_security", "branch_protection_ci")),
    AssessmentArea(34, "Branch-Protection-Evidence", ("branch_protection_ci", "final_go_no_go_scorecard")),
    AssessmentArea(35, "Testabdeckung", ("final_go_no_go_scorecard",)),
    AssessmentArea(36, "Type Safety / Mypy / TS", ("deployment_parity", "supply_chain_security")),
    AssessmentArea(37, "Dependency / Supply-Chain Security", ("supply_chain_security",)),
    AssessmentArea(38, "Docker / Compose / Runtime-Paritaet", ("deployment_parity",)),
    AssessmentArea(39, "Staging-Paritaet", ("deployment_parity",)),
    AssessmentArea(40, "Release / Rollback", ("final_go_no_go_scorecard", "deployment_parity")),
    AssessmentArea(41, "Performance / Load / Capacity", ("observability_slos", "deployment_parity")),
    AssessmentArea(42, "LLM-Orchestrator / KI-Strecken", ("strategy_validation_per_asset_class", "audit_forensics")),
    AssessmentArea(43, "LLM-Safety / Execution Authority", ("live_broker_fail_closed", "audit_forensics")),
    AssessmentArea(44, "Compliance-/Legal-Readiness", ("final_go_no_go_scorecard",)),
    AssessmentArea(45, "Dokumentation / Runbooks", ("final_go_no_go_scorecard", "backup_restore", "disaster_recovery")),
    AssessmentArea(46, "Evidence-Matrix", ("final_go_no_go_scorecard",)),
    AssessmentArea(47, "Production-Readiness-Scorecard", ("final_go_no_go_scorecard",)),
    AssessmentArea(48, "Finaler Go/No-Go-Prozess", ("final_go_no_go_scorecard",)),
    AssessmentArea(49, "Private-Live-Candidate-Readiness", ("final_go_no_go_scorecard", "bitget_exchange_readiness")),
    AssessmentArea(50, "Full-Autonomous-Live-Readiness", ("final_go_no_go_scorecard", "shadow_burn_in")),
)


def _git_value(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _score_for_category(category: CategoryScore | None) -> int:
    if category is None:
        return 2
    if category.status == "verified":
        return 9 if category.blocks_live_trading else 8
    if category.status == "implemented":
        return 6 if category.blocks_live_trading else 7
    if category.status == "partial":
        return 5 if category.blocks_live_trading else 6
    if category.status == "external_required":
        return 5 if category.blocks_live_trading else 6
    return 2


def _area_score(area: AssessmentArea, by_id: dict[str, CategoryScore]) -> int:
    scores = [_score_for_category(by_id.get(category_id)) for category_id in area.category_ids]
    score = round(mean(scores)) if scores else 2
    if any(by_id.get(category_id) and by_id[category_id].blocks_live_trading for category_id in area.category_ids):
        if any(by_id.get(category_id) and by_id[category_id].status != "verified" for category_id in area.category_ids):
            score = min(score, 6)
    if area.number == 50:
        score = min(score, 4)
    return max(1, min(10, score))


def _category_reference(area: AssessmentArea, by_id: dict[str, CategoryScore]) -> str:
    references: list[str] = []
    for category_id in area.category_ids:
        category = by_id.get(category_id)
        if category is None:
            references.append(f"{category_id}=missing")
        else:
            references.append(f"{category_id}={category.status}/{category.decision}/{category.severity}")
    return ", ".join(references)


def _overall_score(area_scores: list[int], scorecard: ReadinessScorecard) -> int:
    score = round(mean(area_scores)) if area_scores else 1
    p0_blockers = [item for item in scorecard.live_blockers if "(P0)" in item]
    if p0_blockers:
        score = min(score, 5)
    if scorecard.private_live_blockers:
        score = min(score, 5)
    return max(1, min(10, score))


def _list_or_default(items: list[str], default: str) -> list[str]:
    return items if items else [default]


def render_master_status(
    scorecard: ReadinessScorecard,
    *,
    completed: list[str] | None = None,
    test_results: list[str] | None = None,
    not_run: list[str] | None = None,
    new_evidence: list[str] | None = None,
    next_step: str | None = None,
) -> str:
    completed = completed or []
    test_results = test_results or []
    not_run = not_run or []
    new_evidence = new_evidence or ["`docs/production_10_10/CURSOR_MASTER_STATUS.md`"]
    next_step = next_step or "P0 zuerst: naechsten groessten Live-Blocker mit Strict-Report, Tests und Evidence-Matrix verknuepfen."
    by_id = {category.id: category for category in scorecard.categories}
    area_rows = [
        (area, _area_score(area, by_id), _category_reference(area, by_id))
        for area in ASSESSMENT_AREAS
    ]
    overall_score = _overall_score([score for _area, score, _ref in area_rows], scorecard)
    p0_blockers = [item for item in scorecard.live_blockers if "(P0)" in item]
    p1_blockers = [item for item in scorecard.live_blockers if "(P1)" in item]
    p2_blockers = [item for item in scorecard.live_blockers if "(P2)" in item]
    status_counts: dict[str, int] = {
        "verified": 0,
        "implemented": 0,
        "external_required": 0,
        "partial": 0,
        "missing": 0,
    }
    for category in scorecard.categories:
        status_counts[category.status] = status_counts.get(category.status, 0) + 1
    mode_by_id = {item.mode: item for item in scorecard.mode_decisions}
    branch = _git_value(["branch", "--show-current"])
    git_sha = _git_value(["rev-parse", "--short", "HEAD"])

    lines = [
        "# Cursor Master Status",
        "",
        "Status: automatisch aus `docs/production_10_10/evidence_matrix.yaml` und der Production-Readiness-Scorecard erzeugt.",
        "",
        "## Durchlauf",
        "",
        f"- Datum/Zeit: `{scorecard.generated_at}`",
        f"- Git-Branch: `{branch}`",
        f"- Git-SHA: `{git_sha}`",
        f"- Gesamt-Score: `{overall_score}/10`",
        f"- Gesamtstatus: `{scorecard.overall_status}`",
        f"- Live-Blocker: `{len(scorecard.live_blockers)}`",
        f"- P0-Blocker: `{len(p0_blockers)}`",
        f"- P1-Blocker: `{len(p1_blockers)}`",
        f"- Private-Live-Blocker: `{len(scorecard.private_live_blockers)}`",
        f"- Asset-Blocker: `{len(scorecard.asset_blockers)}`",
        f"- Verified-Kategorien: `{status_counts.get('verified', 0)}`",
        f"- Implemented-Kategorien: `{status_counts.get('implemented', 0)}`",
        f"- External-Required-Kategorien: `{status_counts.get('external_required', 0)}`",
        "",
        "## Go/No-Go",
        "",
    ]
    for mode in (
        "local_dev",
        "paper",
        "shadow",
        "staging",
        "private_live_candidate",
        "private_live_allowed",
        "full_autonomous_live",
    ):
        decision = mode_by_id[mode]
        lines.append(f"- `{mode}`: `{decision.decision}` - {decision.reason}")

    lines.extend(
        [
            "",
            "## Scores je Bereich",
            "",
            "| Nr. | Bereich | Score | Evidence-Referenz |",
            "| ---: | --- | ---: | --- |",
        ]
    )
    for area, score, reference in area_rows:
        lines.append(f"| {area.number} | {area.title} | `{score}/10` | {reference} |")

    lines.extend(["", "## Offene P0-Luecken", ""])
    lines.extend(f"- `{item}`" for item in p0_blockers[:30])
    if not p0_blockers:
        lines.append("- Keine P0-Luecke erkannt.")

    lines.extend(["", "## Offene P1-Luecken", ""])
    lines.extend(f"- `{item}`" for item in p1_blockers[:30])
    if not p1_blockers:
        lines.append("- Keine P1-Luecke erkannt.")

    lines.extend(["", "## Offene P2-Luecken", ""])
    lines.extend(f"- `{item}`" for item in p2_blockers[:30])
    if not p2_blockers:
        lines.append("- Keine P2-Luecke erkannt.")

    lines.extend(
        [
            "",
            "## In diesem Durchlauf erledigt",
            "",
        ]
    )
    lines.extend(
        f"- {item}"
        for item in _list_or_default(
            completed,
            "`scripts/cursor_master_status.py` erzeugt diesen Master-Status reproduzierbar.",
        )
    )
    lines.extend(
        [
            "",
            "## Tests dieses Durchlaufs",
            "",
        ]
    )
    lines.extend(
        f"- {item}"
        for item in _list_or_default(
            test_results,
            "Noch keine Tests fuer diesen Durchlauf eingetragen.",
        )
    )
    lines.extend(
        [
            "",
            "## Nicht ausgefuehrte Tests",
            "",
        ]
    )
    lines.extend(
        f"- {item}"
        for item in _list_or_default(
            not_run,
            "Noch keine nicht ausgefuehrten Tests eingetragen.",
        )
    )
    lines.extend(
        [
            "",
            "## Neue Evidence",
            "",
            *[f"- {item}" for item in new_evidence],
            "",
            "## Naechster erster Schritt",
            "",
            f"- {next_step}",
            "",
            "## Live-Geld-Entscheidung",
            "",
            "- `private_live_allowed`: `NO_GO`, weil P0/P1-Live-Blocker und externe Evidence fehlen.",
            "- `full_autonomous_live`: `NO_GO`, weil keine lange echte Live-Historie, kein vollstaendiger Owner-Signoff und keine vollstaendig verified Evidence vorliegen.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--completed", action="append", default=[])
    parser.add_argument("--test-result", action="append", default=[])
    parser.add_argument("--not-run", action="append", default=[])
    parser.add_argument("--new-evidence", action="append", default=[])
    parser.add_argument("--next-step")
    args = parser.parse_args(argv)

    scorecard = build_from_repo()
    report = render_master_status(
        scorecard,
        completed=args.completed,
        test_results=args.test_result,
        not_run=args.not_run,
        new_evidence=args.new_evidence or None,
        next_step=args.next_step,
    )
    if args.dry_run:
        print(report)
        return 0
    output = args.output_md
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    try:
        display_path = output.relative_to(ROOT)
    except ValueError:
        display_path = output
    print(f"cursor_master_status: wrote {display_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
