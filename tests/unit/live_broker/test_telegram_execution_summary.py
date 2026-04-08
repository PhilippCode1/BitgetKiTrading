from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_BROKER_SRC = REPO_ROOT / "services" / "live-broker" / "src"
SHARED_SRC = REPO_ROOT / "shared" / "python" / "src"
for candidate in (REPO_ROOT, LIVE_BROKER_SRC, SHARED_SRC):
    s = str(candidate)
    if candidate.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

from live_broker.execution.service import LiveExecutionService

EID = "00000000-0000-0000-0000-000000000099"


def _base_row() -> dict:
    return {
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "direction": "long",
        "decision_action": "live_candidate_recorded",
        "decision_reason": "ok",
        "effective_runtime_mode": "live",
        "requested_runtime_mode": "live",
        "source_service": "signal-engine",
        "source_signal_id": "sig-1",
        "leverage": 10,
        "order_type": "market",
        "created_ts": None,
    }


def test_telegram_summary_eligible_when_live_candidate() -> None:
    repo = MagicMock()
    repo.get_execution_decision.return_value = _base_row()
    repo.get_operator_release.return_value = None
    svc = LiveExecutionService(MagicMock(), MagicMock(), repo)
    out = svc.telegram_operator_release_summary(EID)
    assert out["found"] is True
    assert out["eligible"] is True
    assert out["reason"] == "ok"
    assert out["summary"]["symbol"] == "BTCUSDT"


def test_telegram_summary_not_eligible_when_blocked() -> None:
    row = _base_row()
    row["decision_action"] = "blocked"
    repo = MagicMock()
    repo.get_execution_decision.return_value = row
    repo.get_operator_release.return_value = None
    svc = LiveExecutionService(MagicMock(), MagicMock(), repo)
    out = svc.telegram_operator_release_summary(EID)
    assert out["eligible"] is False
    assert out["reason"] == "not_eligible_for_telegram_release"


def test_telegram_summary_not_eligible_when_already_released() -> None:
    repo = MagicMock()
    repo.get_execution_decision.return_value = _base_row()
    repo.get_operator_release.return_value = {"execution_id": EID}
    svc = LiveExecutionService(MagicMock(), MagicMock(), repo)
    out = svc.telegram_operator_release_summary(EID)
    assert out["eligible"] is False
    assert out["reason"] == "already_released"
