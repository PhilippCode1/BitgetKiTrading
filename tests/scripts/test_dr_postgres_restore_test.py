from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.dr_postgres_restore_test import (
    build_restore_evidence,
    evidence_to_markdown,
    redact_database_url,
)


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dr_postgres_restore_test.py"


def test_dry_run_works() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "dry_run=true" in completed.stdout


def test_production_url_blocked() -> None:
    evidence = build_restore_evidence(
        database_url="postgresql://app:secret@prod-db.internal:5432/app",
        dry_run=False,
        acknowledged_test_db=True,
    )
    assert evidence.status == "FAIL"
    assert "Production-DB" in evidence.message


def test_password_redacted() -> None:
    redacted = redact_database_url("postgresql://user:super-secret@localhost:5432/db")
    assert "super-secret" not in redacted
    assert "[REDACTED]" in redacted


def test_report_contains_rto_rpo() -> None:
    evidence = build_restore_evidence(database_url="", dry_run=True)
    md = evidence_to_markdown(evidence)
    assert "RTO Sekunden" in md
    assert "RPO Sekunden" in md
