#!/usr/bin/env python3
"""Unified private Main Console production readiness scorecard."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "shared" / "python" / "src"
for import_path in (ROOT, SHARED_SRC):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from shared_py.readiness_scorecard import (  # noqa: E402
    PROJECT_NAME,
    ReadinessScorecard,
    build_readiness_scorecard,
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
        lines.append(
            f"- `{category.id}`: `{category.status}` / `{category.decision}` "
            f"/ severity `{category.severity}` / live_blocker `{str(category.blocks_live_trading).lower()}`"
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
    return build_readiness_scorecard(
        matrix,
        git_sha=git_sha(),
        report_names=reports,
        asset_data_quality_verified=False,
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
        print(json.dumps(scorecard_to_console_payload(scorecard), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        suffix = " dry_run=true" if args.dry_run else ""
        print(
            f"production_readiness_scorecard: project={PROJECT_NAME} "
            f"overall={scorecard.overall_status} live_blockers={len(scorecard.live_blockers)} "
            f"asset_blockers={len(scorecard.asset_blockers)}{suffix}"
        )
        private_live = next(item for item in scorecard.mode_decisions if item.mode == "private_live_allowed")
        print(f"private_live_allowed={private_live.decision}")

    if args.strict_live and (scorecard.live_blockers or scorecard.private_live_blockers):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
