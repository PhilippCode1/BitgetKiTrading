#!/usr/bin/env python3
"""Unified private Main Console production readiness scorecard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.readiness_scorecard import (  # noqa: E402
    OWNER_PRIVATE_LIVE_RELEASE_FILENAME,
    PROJECT_NAME,
    ReadinessScorecard,
    build_readiness_scorecard,
    owner_private_live_release_payload_ok,
    scorecard_to_console_payload,
)

DEFAULT_MATRIX = ROOT / "docs" / "production_10_10" / "evidence_matrix.yaml"
REPORTS_DIR = ROOT / "reports"


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()
    except Exception:
        return "unknown"


def load_evidence_matrix(path: Path = DEFAULT_MATRIX) -> dict[str, Any]:
    if not path.is_file():
        return {"categories": []}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return {"categories": []}
    return loaded


def detect_report_names(reports_dir: Path = REPORTS_DIR) -> list[str]:
    if not reports_dir.is_dir():
        return []
    return sorted(path.name for path in reports_dir.glob("*.md"))


def load_report_payloads(reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    asset_preflight = reports_dir / "asset_preflight_evidence.json"
    if asset_preflight.is_file():
        try:
            loaded = json.loads(asset_preflight.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            payloads["asset_preflight_evidence"] = loaded
    demo_lifecycle = reports_dir / "demo_lifecycle_evidence.json"
    if demo_lifecycle.is_file():
        try:
            loaded = json.loads(demo_lifecycle.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, dict):
            payloads["demo_lifecycle_evidence"] = loaded
    return payloads


def load_owner_private_live_release_confirmed(reports_dir: Path = REPORTS_DIR) -> bool:
    path = reports_dir / OWNER_PRIVATE_LIVE_RELEASE_FILENAME
    if not path.is_file():
        return False
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return owner_private_live_release_payload_ok(loaded)


def scorecard_to_markdown(scorecard: ReadinessScorecard) -> str:
    lines = [
        "# Production Readiness Scorecard",
        "",
        f"- Datum/Zeit: `{scorecard.generated_at}`",
        f"- Git SHA: `{scorecard.git_sha}`",
        f"- Projektname: `{scorecard.project}`",
        f"- Gesamtstatus: `{scorecard.overall_status}`",
        f"- Owner-Signoff-Feld: `{scorecard.owner_signoff}`",
        "",
        "## Modusentscheidungen",
        "",
    ]
    for item in scorecard.mode_decisions:
        lines.append(f"- `{item.mode}`: `{item.decision}` - {item.reason}")
    lines.extend(["", "## Kategorieuebersicht", ""])
    for category in scorecard.categories:
        lb = str(category.blocks_live_trading).lower()
        lines.append(
            f"- `{category.id}`: `{category.status}` / `{category.decision}` / "
            f"severity `{category.severity}` / live_blocker `{lb}`"
        )
    lines.extend(["", "## Live-Blocker", ""])
    lines.extend(f"- `{item}`" for item in scorecard.live_blockers)
    lines.extend(["", "## Private-Live-Blocker", ""])
    lines.extend(f"- `{item}`" for item in scorecard.private_live_blockers)
    lines.extend(["", "## Asset-Blocker", ""])
    lines.extend(f"- `{item}`" for item in scorecard.asset_blockers)
    lines.extend(["", "## Fehlende Evidence", ""])
    lines.extend(f"- `{item}`" for item in scorecard.missing_evidence)
    lines.extend(["", "## Naechste Schritte", ""])
    lines.extend(f"- {item}" for item in scorecard.next_steps)
    lines.extend(
        [
            "",
            "## Maschinelle Owner-Freigabe (Private Live)",
            "",
            "- `owner_private_live_release_confirmed`: "
            f"`{str(scorecard.owner_private_live_release_confirmed).lower()}`",
            "- Erwartete lokale Datei (gitignored): "
            f"`reports/{OWNER_PRIVATE_LIVE_RELEASE_FILENAME}`",
            "- Template: "
            "`docs/production_10_10/owner_private_live_release.template.json`",
            "",
            "## Owner-Signoff",
            "",
            "- Philipp Crljic Entscheidung: `PENDING`",
            "- Datum:",
            "- Signatur/Referenz:",
            "",
        ]
    )
    return "\n".join(lines)


def build_from_repo() -> ReadinessScorecard:
    matrix = load_evidence_matrix()
    reports = detect_report_names()
    payloads = load_report_payloads()
    owner_ok = load_owner_private_live_release_confirmed()
    return build_readiness_scorecard(
        matrix,
        git_sha=git_sha(),
        report_names=reports,
        asset_data_quality_verified=False,
        report_payloads=payloads,
        owner_private_live_release_confirmed=owner_ok,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict-live", action="store_true")
    args = parser.parse_args(argv)

    scorecard = build_from_repo()
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(scorecard_to_markdown(scorecard), encoding="utf-8")

    if args.json:
        payload = scorecard_to_console_payload(scorecard)
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        suffix = " dry_run=true" if args.dry_run else ""
        n_lb = len(scorecard.live_blockers)
        n_ab = len(scorecard.asset_blockers)
        print(
            f"production_readiness_scorecard: project={PROJECT_NAME} "
            f"overall={scorecard.overall_status} live_blockers={n_lb} "
            f"asset_blockers={n_ab}{suffix}"
        )
        private_live = next(
            item
            for item in scorecard.mode_decisions
            if item.mode == "private_live_allowed"
        )
        print(f"private_live_allowed={private_live.decision}")

    has_blockers = scorecard.live_blockers or scorecard.private_live_blockers
    if args.strict_live and has_blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
