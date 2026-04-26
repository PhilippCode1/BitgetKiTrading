from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.cursor_master_status import ASSESSMENT_AREAS, render_master_status
from shared_py.readiness_scorecard import REQUIRED_CATEGORIES, build_readiness_scorecard


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "cursor_master_status.py"


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
                "next_action": f"{category_id} evidence.",
            }
            for category_id, title in REQUIRED_CATEGORIES
        ]
    }


def _all_reports() -> list[str]:
    return [
        "bitget_readiness.md",
        "dr_restore_test.md",
        "shadow_burn_in.md",
        "live_safety_drill.md",
        "production_readiness_scorecard.md",
    ]


def test_assessment_area_count_matches_prompt() -> None:
    assert len(ASSESSMENT_AREAS) == 50
    assert ASSESSMENT_AREAS[0].title == "Produktziel und Scope-Klarheit"
    assert ASSESSMENT_AREAS[-1].title == "Full-Autonomous-Live-Readiness"


def test_master_status_contains_required_sections() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(status="partial", overrides={"private_owner_scope": "verified"}),
        report_names=[],
        asset_data_quality_verified=False,
    )
    report = render_master_status(scorecard)
    for heading in (
        "Durchlauf",
        "Go/No-Go",
        "Scores je Bereich",
        "Offene P0-Luecken",
        "Tests dieses Durchlaufs",
        "Neue Evidence",
        "Naechster erster Schritt",
        "Live-Geld-Entscheidung",
    ):
        assert heading in report
    for metric in (
        "P0-Blocker",
        "P1-Blocker",
        "Verified-Kategorien",
        "Implemented-Kategorien",
        "External-Required-Kategorien",
    ):
        assert metric in report
    assert "`private_live_allowed`: `NO_GO`" in report
    assert "`full_autonomous_live`: `NO_GO`" in report


def test_master_status_accepts_dynamic_evidence_and_next_step() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(status="partial", overrides={"private_owner_scope": "verified"}),
        report_names=[],
        asset_data_quality_verified=False,
    )
    report = render_master_status(
        scorecard,
        new_evidence=["`reports/risk_execution_evidence.md`"],
        next_step="P0 zuerst: Main-Console-Safety-State-Evidence ausbauen.",
    )
    assert "`reports/risk_execution_evidence.md`" in report
    assert "P0 zuerst: Main-Console-Safety-State-Evidence ausbauen." in report


def test_full_autonomous_live_score_is_capped_even_with_verified_matrix() -> None:
    scorecard = build_readiness_scorecard(
        _matrix(),
        report_names=_all_reports(),
        asset_data_quality_verified=True,
    )
    report = render_master_status(scorecard)
    assert "| 50 | Full-Autonomous-Live-Readiness | `4/10` |" in report


def test_cli_writes_master_status(tmp_path: Path) -> None:
    output = tmp_path / "CURSOR_MASTER_STATUS.md"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-md", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0
    assert output.is_file()
    content = output.read_text(encoding="utf-8")
    assert "# Cursor Master Status" in content
    assert "private_live_allowed" in content
