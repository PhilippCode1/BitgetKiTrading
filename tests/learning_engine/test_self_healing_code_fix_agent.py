from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from learning_engine.config import LearningEngineSettings
from learning_engine.self_healing.code_fix_agent import (
    run_self_healing_for_system_alert,
)
from learning_engine.self_healing.protocol import RepairLLMOutput, SandboxTestResult
from monitor_engine.checks.self_healing_canary import collect_self_healing_canary_alerts
from monitor_engine.config import MonitorEngineSettings
from shared_py.eventbus.envelope import EventEnvelope


def test_monitor_canary_disabled_by_default() -> None:
    s = MonitorEngineSettings()
    assert collect_self_healing_canary_alerts(s) == []


def test_monitor_canary_contains_wrong_and_expected_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MONITOR_SELF_HEALING_CANARY_ENABLED", "true")
    s = MonitorEngineSettings()
    specs = collect_self_healing_canary_alerts(s)
    assert len(specs) == 1
    st = str(specs[0].details.get("stacktrace", ""))
    assert "wrong-mix/market/tickers" in st
    assert specs[0].details.get("expected_path_segment") == "mix/market/tickers"


@patch("learning_engine.self_healing.code_fix_agent.run_tests_in_sandbox")
@patch("learning_engine.self_healing.code_fix_agent._publish_operator_proposal")
@patch("learning_engine.self_healing.code_fix_agent._store_apply_token")
@patch(
    "learning_engine.self_healing.code_fix_agent.reserve_alert_processing",
    return_value=True,
)
@patch("learning_engine.self_healing.code_fix_agent._call_llm_repair_plan")
def test_self_healing_llm_proposes_correct_path_segment(
    mock_llm: MagicMock,
    _reserve: MagicMock,
    _store: MagicMock,
    _pub: MagicMock,
    mock_sb: MagicMock,
) -> None:
    mock_sb.return_value = SandboxTestResult(
        exit_code=0, stdout_tail="ok", stderr_tail="", command_de="pytest -q"
    )
    mock_llm.return_value = RepairLLMOutput(
        hypothesis_de="Falscher REST-Pfad: wrong-mix statt mix.",
        root_cause_tags=["api_path"],
        proposed_unified_diff=(
            "--- a/services/demo.txt\n+++ b/services/demo.txt\n@@\n"
            "-wrong-mix/market/tickers\n+mix/market/tickers\n"
        ),
        recommended_verify_command_de="pytest tests/unit -q",
        confidence_0_1=0.82,
    )

    settings = LearningEngineSettings()
    env = EventEnvelope(
        event_type="system_alert",
        payload={
            "alert_key": "CRITICAL_RUNTIME_EXCEPTION",
            "severity": "critical",
            "title": "t",
            "message": "m",
            "details": {
                "stacktrace": "httpx.HTTPStatusError: 404 ... wrong-mix/market/tickers",
            },
        },
    )

    out = run_self_healing_for_system_alert(settings, env)
    assert out.status == "tests_passed"
    assert "mix/market/tickers" in out.proposed_unified_diff
    mock_llm.assert_called_once()
    _pub.assert_called_once()
