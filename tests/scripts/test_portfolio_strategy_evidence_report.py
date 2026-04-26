from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.portfolio_strategy_evidence_report import (
    REQUIRED_MULTI_ASSET_STRATEGY_REASONS,
    REQUIRED_PORTFOLIO_BLOCK_REASONS,
    REQUIRED_STRATEGY_BLOCK_REASONS,
    assess_external_evidence,
    build_external_evidence_template,
    build_report_payload,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "portfolio_strategy_evidence_report.py"


def _verified_external_payload() -> dict[str, object]:
    payload = build_external_evidence_template()
    payload.update(
        {
            "status": "verified",
            "evidence_environment": "staging-shadow",
            "git_sha": "abc1234",
            "generated_at": "2026-04-26T00:00:00Z",
        }
    )
    payload["owner_limits"] = {
        "signed_by": "Philipp Crljic",
        "signed_at": "2026-04-26T00:00:00Z",
        "max_total_notional": 20000.0,
        "max_margin_usage": 0.4,
        "max_family_exposure": 15000.0,
        "max_net_directional_exposure": 12000.0,
        "max_correlation_stress": 0.75,
        "document_uri": "evidence://owner-limits/portfolio-v1",
    }
    payload["portfolio_drill"] = {
        "runtime_snapshot_fresh": True,
        "missing_snapshot_blocks_live": True,
        "stale_snapshot_blocks_live": True,
        "exposure_limit_blocks_live": True,
        "correlation_unknown_blocks_live": True,
        "family_exposure_blocks_live": True,
        "pending_orders_counted_in_exposure": True,
        "live_orders_submitted_during_drill": False,
        "report_uri": "evidence://portfolio-drill/report",
    }
    payload["strategy_validation"] = {
        "asset_classes_covered": ["major_high_liquidity", "new_listing"],
        "backtest_reports_present": True,
        "walk_forward_reports_present": True,
        "paper_reports_present": True,
        "shadow_reports_present": True,
        "slippage_fees_funding_included": True,
        "drawdown_limits_passed": True,
        "no_trade_quality_checked": True,
        "lineage_documented": True,
        "report_uri": "evidence://strategy-validation/report",
    }
    payload["shadow_burn_in"] = {
        "real_shadow_period_started_at": "2026-04-01T00:00:00Z",
        "real_shadow_period_ended_at": "2026-04-25T00:00:00Z",
        "shadow_passed": True,
        "divergence_report_uri": "evidence://shadow/divergence",
    }
    payload["safety"] = {
        "secrets_redacted": True,
        "real_orders_possible": False,
        "operator_approval_record_uri": "evidence://operator-approval",
    }
    return payload


def test_report_keeps_live_no_go_and_covers_required_internal_reasons() -> None:
    payload = build_report_payload()

    assert payload["private_live_decision"] == "NO_GO"
    assert payload["full_autonomous_live"] == "NO_GO"
    assert payload["external_evidence_assessment"]["status"] == "FAIL"
    assert payload["missing_portfolio_block_reasons"] == []
    assert payload["missing_strategy_block_reasons"] == []
    assert payload["missing_multi_asset_strategy_reasons"] == []
    assert payload["missing_live_preflight_reasons"] == []

    assert set(REQUIRED_PORTFOLIO_BLOCK_REASONS).issubset(payload["covered_portfolio_block_reasons"])
    assert set(REQUIRED_STRATEGY_BLOCK_REASONS).issubset(payload["covered_strategy_block_reasons"])
    assert set(REQUIRED_MULTI_ASSET_STRATEGY_REASONS).issubset(payload["covered_multi_asset_strategy_reasons"])
    assert {"portfolio_risk_not_safe", "strategy_evidence_missing_or_invalid"}.issubset(
        payload["covered_live_preflight_reasons"]
    )


def test_portfolio_and_strategy_scenarios_fail_closed() -> None:
    payload = build_report_payload()

    assert all(row["preflight"]["submit_allowed"] is False for row in payload["portfolio_scenarios"])
    assert any("account_equity_ungueltig" in row["block_reasons"] for row in payload["portfolio_scenarios"])
    assert any("zu_viele_pending_orders" in row["block_reasons"] for row in payload["portfolio_scenarios"])
    assert any("family_exposure_zu_hoch" in row["block_reasons"] for row in payload["portfolio_scenarios"])

    blocking_strategy_rows = [row for row in payload["strategy_asset_scenarios"] if row["blocks_live"]]
    assert blocking_strategy_rows
    assert all(row["preflight"]["submit_allowed"] is False for row in blocking_strategy_rows)
    assert any("strategy_evidence_expired" in row["block_reasons"] for row in blocking_strategy_rows)

    failing_multi_asset_rows = [row for row in payload["multi_asset_strategy_scenarios"] if row["verdict"] == "FAIL"]
    assert failing_multi_asset_rows
    assert all(row["preflight"]["submit_allowed"] is False for row in failing_multi_asset_rows)


def test_external_template_fails_until_real_evidence_is_supplied() -> None:
    assessment = assess_external_evidence(build_external_evidence_template())

    assert assessment["status"] == "FAIL"
    assert assessment["external_required"] is True
    assert "external_status_nicht_verified" in assessment["failures"]
    assert "portfolio_drill_missing_snapshot_blocks_live_nicht_belegt" in assessment["failures"]
    assert "strategy_validation_shadow_reports_present_nicht_belegt" in assessment["failures"]


def test_external_verified_payload_passes_without_secrets() -> None:
    assessment = assess_external_evidence(_verified_external_payload())

    assert assessment["status"] == "PASS"
    assert assessment["external_required"] is False
    assert assessment["failures"] == []


def test_external_evidence_rejects_live_orders_and_secret_surfaces() -> None:
    payload = _verified_external_payload()
    payload["portfolio_drill"]["live_orders_submitted_during_drill"] = True  # type: ignore[index]
    payload["api_key"] = "real-looking-value"

    assessment = assess_external_evidence(payload)

    assert assessment["status"] == "FAIL"
    assert "portfolio_drill_darf_keine_live_orders_senden" in assessment["failures"]
    assert any("api_key" in issue for issue in assessment["failures"])


def test_cli_writes_report_and_template(tmp_path: Path) -> None:
    out_md = tmp_path / "portfolio_strategy.md"
    out_json = tmp_path / "portfolio_strategy.json"
    template = tmp_path / "template.json"

    template_proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--write-template", str(template)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert template_proc.returncode == 0
    assert json.loads(template.read_text(encoding="utf-8"))["schema_version"] == 1

    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--strict",
            "--output-md",
            str(out_md),
            "--output-json",
            str(out_json),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "portfolio_strategy_evidence_report" in proc.stdout
    assert "# Portfolio Strategy Evidence Report" in out_md.read_text(encoding="utf-8")
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["missing_live_preflight_reasons"] == []
