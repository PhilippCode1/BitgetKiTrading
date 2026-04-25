from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.production_readiness_scorecard import scorecard_to_markdown
from shared_py.readiness_scorecard import REQUIRED_CATEGORIES, build_readiness_scorecard


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "production_readiness_scorecard.py"


def _matrix(status: str = "verified", overrides: dict[str, str] | None = None) -> dict[str, object]:
    overrides = overrides or {}
    return {
        "categories": [
            {
                "id": category_id,
                "title": title,
                "status": overrides.get(category_id, status),
                "severity": "P0",
                "blocks_live_trading": category_id != "private_owner_scope",
                "next_action": f"{category_id} abschliessen.",
            }
            for category_id, title in REQUIRED_CATEGORIES
        ]
    }


def _mode(scorecard, mode: str) -> str:
    return next(item.decision for item in scorecard.mode_decisions if item.mode == mode)


def test_dry_run_works() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "production_readiness_scorecard" in completed.stdout


def test_json_output_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["project"] == "bitget-btc-ai"
    assert "private_live_allowed" in payload["allows"]


def test_report_contains_required_sections() -> None:
    scorecard = build_readiness_scorecard(_matrix(), report_names=["bitget_readiness.md", "dr_restore_test.md", "shadow_burn_in.md", "live_safety_drill.md", "production_readiness_scorecard.md"], asset_data_quality_verified=True)
    report = scorecard_to_markdown(scorecard)
    for heading in (
        "Datum/Zeit",
        "Git SHA",
        "Projektname",
        "Gesamtstatus",
        "Modusentscheidungen",
        "Kategorieuebersicht",
        "Live-Blocker",
        "Private-Live-Blocker",
        "Asset-Blocker",
        "Fehlende Evidence",
        "Naechste Schritte",
        "Owner-Signoff",
    ):
        assert heading in report


def test_strict_live_exit_1_with_blockers() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--strict-live"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1


def test_no_billing_customer_categories_required() -> None:
    category_ids = {category_id for category_id, _title in REQUIRED_CATEGORIES}
    assert "billing" not in category_ids
    assert "customer" not in category_ids
    assert "payment_provider_checks" not in category_ids
