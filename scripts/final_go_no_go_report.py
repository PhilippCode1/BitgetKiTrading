#!/usr/bin/env python3
"""Finale 10/10 Go/No-Go-Pruefung fuer private Live-Kandidatur."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
REPORTS = ROOT / "reports"
OWNER_RELEASE = REPORTS / "owner_private_live_release.json"


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _load_matrix() -> list[dict[str, Any]]:
    loaded = yaml.safe_load(MATRIX.read_text(encoding="utf-8")) or {}
    categories = loaded.get("categories") if isinstance(loaded, dict) else []
    return [item for item in categories if isinstance(item, dict)]


def _load_owner_release() -> dict[str, Any] | None:
    if not OWNER_RELEASE.is_file():
        return None
    try:
        loaded = json.loads(OWNER_RELEASE.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _existing_report(name: str) -> bool:
    return (REPORTS / name).is_file()


def _score_from_counts(*, verified: int, implemented: int, external_required: int, total: int, p0: int) -> int:
    if total <= 0:
        return 1
    base = int(round((verified / total) * 10))
    if p0 > 0:
        base = min(base, 5)
    elif external_required > 0:
        base = min(base, 7)
    elif implemented > 0:
        base = min(base, 8)
    return max(1, min(10, base))


def build_payload() -> dict[str, Any]:
    categories = _load_matrix()
    by_id = {str(item.get("id")): item for item in categories}
    status_counts = {"verified": 0, "implemented": 0, "external_required": 0, "missing": 0, "partial": 0}
    open_p0: list[str] = []
    open_p1: list[str] = []
    external_points: list[str] = []
    for category in categories:
        cid = str(category.get("id"))
        status = str(category.get("status") or "missing")
        severity = str(category.get("severity") or "P0")
        blocks_live = bool(category.get("blocks_live_trading", True))
        if status in status_counts:
            status_counts[status] += 1
        if blocks_live and status != "verified":
            item = f"{cid}:{status}:{severity}"
            if severity == "P0":
                open_p0.append(item)
            elif severity == "P1":
                open_p1.append(item)
        if status == "external_required":
            external_points.append(cid)

    required_report_files = [
        "branch_protection_ci_evidence.json",
        "secrets_vault_rotation_evidence.json",
        "bitget_runtime_readiness.json",
        "bitget_exchange_instrument_evidence.json",
        "bitget_key_permission_evidence.json",
        "asset_governance_evidence.json",
        "asset_preflight_evidence.json",
        "asset_data_quality.json",
        "liquidity_spread_slippage_evidence.json",
        "risk_execution_evidence.json",
        "portfolio_risk_drill.json",
        "strategy_asset_evidence.json",
        "multi_asset_strategy_evidence.json",
        "live_broker_fail_closed_evidence.json",
        "reconcile_idempotency_summary.json",
        "reconcile_truth_drill.json",
        "live_safety_evidence.json",
        "backup_dr_evidence.json",
        "postgres_restore_drill.json",
        "disaster_recovery_drill.json",
        "observability_alert_evidence.json",
        "incident_drill.json",
    ]
    missing_runtime_reports = [name for name in required_report_files if not _existing_report(name)]

    owner = _load_owner_release()
    owner_missing = []
    if not owner:
        owner_missing.append("owner_private_live_release_missing")
    else:
        if str(owner.get("owner_decision") or "").upper() != "GO":
            owner_missing.append("owner_decision_not_go")
        if owner.get("full_autonomous_live_allowed") is not False:
            owner_missing.append("full_autonomous_live_allowed_must_be_false")
        if not str(owner.get("signature_reference") or "").strip():
            owner_missing.append("signature_reference_missing")

    total = len(categories)
    software_score = 8 if not missing_runtime_reports else 7
    evidence_score = _score_from_counts(
        verified=status_counts["verified"],
        implemented=status_counts["implemented"],
        external_required=status_counts["external_required"],
        total=total,
        p0=len(open_p0),
    )
    private_live_score = 2 if open_p0 else (4 if owner_missing else 8)
    autonomous_score = 1
    overall_score = max(1, round((software_score + evidence_score + private_live_score + autonomous_score) / 4))

    private_candidate = "NO" if open_p0 else "YES"
    private_allowed = "YES" if (not open_p0 and not open_p1 and not owner_missing and not missing_runtime_reports) else "NO"
    full_auto = "NO"
    allowed_next_mode = "shadow" if open_p0 else "private_live_candidate"

    return {
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "git_sha": _git_sha(),
        "branch": _git_branch(),
        "project_name": "bitget-btc-ai",
        "overall_status": "NO_GO" if private_allowed == "NO" else "GO_WITH_WARNINGS",
        "overall_score_1_10": overall_score,
        "software_score": software_score,
        "evidence_score": evidence_score,
        "private_live_readiness_score": private_live_score,
        "full_autonomous_live_score": autonomous_score,
        "status_counts": status_counts,
        "open_p0_blockers": open_p0,
        "open_p1_blockers": open_p1,
        "external_required_points": external_points,
        "missing_runtime_evidence": missing_runtime_reports,
        "missing_owner_evidence": owner_missing,
        "mode_decisions": {
            "local_dev": "GO_WITH_WARNINGS",
            "paper": "GO",
            "shadow": "GO_WITH_WARNINGS",
            "staging": "NOT_ENOUGH_EVIDENCE",
            "private_live_candidate": private_candidate,
            "private_live_allowed": private_allowed,
            "full_autonomous_live": full_auto,
        },
        "allowed_next_mode": allowed_next_mode,
        "strict_reasoning": [
            "implemented wird nie als verified gezaehlt",
            "external_required wird nie als verified gezaehlt",
            "private_live_allowed bleibt NO bei offenen P0/P1 oder fehlendem Owner-Signoff",
            "full_autonomous_live bleibt NO ohne lange echte Live-Historie",
        ],
        "next_steps": [
            "Offene P0/P1 Kategorien mit Runtime-Evidence auf verified bringen",
            "Owner-Release extern signieren und lokal gitignored ablegen",
            "Staging-Drills fuer Alert/SLO/Restore/Shadow-Burn-in extern nachweisen",
        ],
        "categories": [
            {
                "id": str(item.get("id")),
                "status": str(item.get("status") or "missing"),
                "severity": str(item.get("severity") or "P0"),
                "blocks_live_trading": bool(item.get("blocks_live_trading", True)),
            }
            for item in categories
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Final Go / No-Go Report",
        "",
        f"- Datum/Zeit: `{payload['generated_at']}`",
        f"- Git SHA: `{payload['git_sha']}`",
        f"- Branch: `{payload['branch']}`",
        f"- Projekt: `{payload['project_name']}`",
        f"- Gesamtstatus: `{payload['overall_status']}`",
        f"- Gesamt-Score: `{payload['overall_score_1_10']}/10`",
        f"- Software-Score: `{payload['software_score']}/10`",
        f"- Evidence-Score: `{payload['evidence_score']}/10`",
        f"- Private-Live-Readiness-Score: `{payload['private_live_readiness_score']}/10`",
        f"- Full-Autonomous-Live-Score: `{payload['full_autonomous_live_score']}/10`",
        "",
        "## Modusentscheidungen",
        "",
    ]
    for key, value in payload["mode_decisions"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Offene P0-Blocker", ""])
    lines.extend(f"- `{x}`" for x in (payload["open_p0_blockers"] or ["none"]))
    lines.extend(["", "## Offene P1-Blocker", ""])
    lines.extend(f"- `{x}`" for x in (payload["open_p1_blockers"] or ["none"]))
    lines.extend(["", "## Fehlende Runtime-Evidence", ""])
    lines.extend(f"- `{x}`" for x in (payload["missing_runtime_evidence"] or ["none"]))
    lines.extend(["", "## Fehlende Owner-Evidence", ""])
    lines.extend(f"- `{x}`" for x in (payload["missing_owner_evidence"] or ["none"]))
    lines.extend(["", "## Strikte Begruendung", ""])
    lines.extend(f"- {x}" for x in payload["strict_reasoning"])
    lines.extend(["", "## Naechste konkrete Schritte", ""])
    lines.extend(f"- {x}" for x in payload["next_steps"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)

    payload = build_payload()
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "final_go_no_go_report: "
        f"score={payload['overall_score_1_10']} "
        f"p0={len(payload['open_p0_blockers'])} "
        f"private_live_allowed={payload['mode_decisions']['private_live_allowed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
