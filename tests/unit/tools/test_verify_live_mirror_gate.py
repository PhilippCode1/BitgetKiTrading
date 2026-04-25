from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_live_mirror_gate import evaluate


def test_evaluate_reports_not_ready_for_shadow_template() -> None:
    env = {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "EXECUTION_MODE": "shadow",
        "LIVE_TRADE_ENABLE": "false",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_REQUIRE_EXECUTION_BINDING": "true",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "true",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "true",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "7",
        "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE": "7",
        "BITGET_DEMO_ENABLED": "false",
        "NEWS_FIXTURE_MODE": "false",
        "LLM_USE_FAKE_PROVIDER": "false",
        "PAPER_SIM_MODE": "false",
    }
    out = evaluate(env)
    assert out["verdict"] == "NOT_READY"
    assert any("EXECUTION_MODE" in reason for reason in out["not_ready_reasons"])


def test_evaluate_reports_fail_for_fake_or_local_production_values() -> None:
    env = {
        "PRODUCTION": "true",
        "APP_ENV": "production",
        "EXECUTION_MODE": "live",
        "LIVE_TRADE_ENABLE": "true",
        "LIVE_BROKER_ENABLED": "true",
        "LIVE_REQUIRE_EXECUTION_BINDING": "true",
        "LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN": "true",
        "REQUIRE_SHADOW_MATCH_BEFORE_LIVE": "true",
        "LIVE_KILL_SWITCH_ENABLED": "true",
        "RISK_HARD_GATING_ENABLED": "true",
        "RISK_REQUIRE_7X_APPROVAL": "true",
        "RISK_ALLOWED_LEVERAGE_MIN": "7",
        "RISK_ALLOWED_LEVERAGE_MAX": "7",
        "RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE": "7",
        "BITGET_DEMO_ENABLED": "false",
        "NEWS_FIXTURE_MODE": "false",
        "LLM_USE_FAKE_PROVIDER": "false",
        "PAPER_SIM_MODE": "false",
        "BITGET_API_BASE_URL": "https://api.demo-provider.local",
    }
    out = evaluate(env)
    assert out["verdict"] == "FAIL"
    assert out["production_smells"]
