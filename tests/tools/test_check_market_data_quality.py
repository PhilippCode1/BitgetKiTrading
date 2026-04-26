from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tools.check_market_data_quality import analyze_market_data_quality


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "check_market_data_quality.py"


def test_tool_runs_and_returns_structure() -> None:
    report = ROOT / "reports" / "asset_data_quality.json"
    summary = analyze_market_data_quality(report_path=report)
    assert "ok" in summary
    assert "issues" in summary
    assert "error_count" in summary
    assert "report_path" in summary


def test_json_output_is_parseable() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    parsed = __import__("json").loads(completed.stdout)
    assert "report_path" in parsed
    assert "issues" in parsed


def test_strict_live_fails_without_runtime_evidence(tmp_path: Path) -> None:
    report = tmp_path / "asset_data_quality.json"
    report.write_text(
        __import__("json").dumps(
            {
                "asset": "BTCUSDT",
                "market_family": "futures",
                "status": "not_enough_evidence",
                "live_allowed": False,
                "paper_allowed": True,
                "shadow_allowed": True,
                "reasons": ["runtime_evidence_missing"],
                "freshness": {},
                "gaps": {},
                "plausibility": {},
                "cross_source": {"exchange_truth_checked": False},
                "checked_at": "2026-01-01T00:00:00+00:00",
                "evidence_level": "synthetic",
            }
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(TOOL), "--report", str(report), "--strict-live"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
