#!/usr/bin/env python3
"""Safe Postgres restore evidence adapter for private live approval."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RestoreEvidence:
    status: str
    generated_at: str
    git_sha: str
    dry_run: bool
    database_url_redacted: str
    rto_seconds: float | None
    rpo_seconds: float | None
    live_ready: bool
    message: str


def redact_database_url(url: str) -> str:
    if not url:
        return ""
    return re.sub(r"(?i)([a-z0-9+]+://[^:/@\s]+:)([^@\s]+)(@)", r"\1[REDACTED]\3", url)


def is_production_database_url(url: str) -> bool:
    lowered = url.lower()
    production_markers = ("prod", "production", "rds.amazonaws.com", "azure.com", "cloudsql")
    test_markers = ("test", "staging", "shadow", "local", "localhost", "127.0.0.1")
    return any(marker in lowered for marker in production_markers) and not any(
        marker in lowered for marker in test_markers
    )


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


def build_restore_evidence(
    *,
    database_url: str = "",
    dry_run: bool,
    acknowledged_test_db: bool = False,
) -> RestoreEvidence:
    if database_url and is_production_database_url(database_url):
        return RestoreEvidence(
            status="FAIL",
            generated_at=datetime.now(tz=UTC).isoformat(),
            git_sha=git_sha(),
            dry_run=dry_run,
            database_url_redacted=redact_database_url(database_url),
            rto_seconds=None,
            rpo_seconds=None,
            live_ready=False,
            message="Production-DB wird fuer Restore-Test blockiert.",
        )
    if not dry_run and not acknowledged_test_db:
        return RestoreEvidence(
            status="FAIL",
            generated_at=datetime.now(tz=UTC).isoformat(),
            git_sha=git_sha(),
            dry_run=False,
            database_url_redacted=redact_database_url(database_url),
            rto_seconds=None,
            rpo_seconds=None,
            live_ready=False,
            message="Nicht-dry-run verlangt --i-understand-this-is-a-test-db.",
        )
    return RestoreEvidence(
        status="DRY_RUN" if dry_run else "EXTERNAL_REQUIRED",
        generated_at=datetime.now(tz=UTC).isoformat(),
        git_sha=git_sha(),
        dry_run=dry_run,
        database_url_redacted=redact_database_url(database_url),
        rto_seconds=0.0 if dry_run else None,
        rpo_seconds=0.0 if dry_run else None,
        live_ready=False,
        message=(
            "Dry-run: keine DB-Mutation. Echter Restore-Report mit RTO/RPO bleibt Pflicht."
            if dry_run
            else "Test-DB bestaetigt; echter Restore-Run muss extern ausgefuehrt und archiviert werden."
        ),
    )


def evidence_to_markdown(evidence: RestoreEvidence) -> str:
    payload = asdict(evidence)
    return "\n".join(
        [
            "# Postgres Restore Test Evidence",
            "",
            f"- Datum/Zeit: `{evidence.generated_at}`",
            f"- Git SHA: `{evidence.git_sha}`",
            f"- Status: `{evidence.status}`",
            f"- Dry-run: `{str(evidence.dry_run).lower()}`",
            f"- Database URL: `{evidence.database_url_redacted or 'nicht gesetzt'}`",
            f"- RTO Sekunden: `{evidence.rto_seconds}`",
            f"- RPO Sekunden: `{evidence.rpo_seconds}`",
            f"- Live-ready: `{str(evidence.live_ready).lower()}`",
            f"- Aussage: {evidence.message}",
            "",
            "## Redacted JSON",
            "```json",
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
            "```",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--i-understand-this-is-a-test-db", action="store_true")
    args = parser.parse_args(argv)
    evidence = build_restore_evidence(
        database_url=args.database_url,
        dry_run=args.dry_run,
        acknowledged_test_db=args.i_understand_this_is_a_test_db,
    )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(evidence_to_markdown(evidence), encoding="utf-8")
    if args.json:
        print(json.dumps(asdict(evidence), indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            f"dr_postgres_restore_test: status={evidence.status} "
            f"dry_run={str(evidence.dry_run).lower()} live_ready=false"
        )
        print(evidence.message)
    return 1 if evidence.status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
