from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "docs" / "production_10_10" / "owner_private_live_release.template.json"


def test_owner_release_template_contains_required_fields() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    required = [
        "owner_name",
        "owner_email",
        "project_name",
        "git_sha",
        "release_candidate_version",
        "environment",
        "allowed_mode",
        "allowed_assets",
        "allowed_market_families",
        "max_leverage_initial",
        "max_notional_total",
        "max_daily_loss",
        "max_weekly_loss",
        "max_drawdown",
        "shadow_burn_in_report_ref",
        "bitget_readiness_report_ref",
        "restore_report_ref",
        "live_safety_report_ref",
        "alert_report_ref",
        "branch_protection_report_ref",
        "legal_risk_acknowledged",
        "no_withdraw_permission_confirmed",
        "live_is_private_owner_only",
        "full_autonomous_live_allowed",
        "owner_decision",
        "signed_at",
        "signature_reference",
    ]
    for key in required:
        assert key in payload
    assert payload["full_autonomous_live_allowed"] is False
