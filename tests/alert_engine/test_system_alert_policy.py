from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ALERT_ENGINE_SRC = ROOT / "services" / "alert-engine" / "src"
for candidate in (ROOT / "shared" / "python" / "src", ALERT_ENGINE_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from alert_engine.alerts.policies import evaluate_system_alert
from shared_py.eventbus import EventEnvelope


def test_system_alert_uses_envelope_dedupe_and_live_broker_type() -> None:
    env = EventEnvelope(
        event_type="system_alert",
        dedupe_key="live-broker:kill-switch:service:armed",
        payload={
            "severity": "critical",
            "title": "live-broker kill switch armed",
            "message": "Kill switch aktiv",
            "details": {"scope": "service"},
        },
    )
    intents = evaluate_system_alert(env)
    assert len(intents) == 1
    intent = intents[0]
    assert intent.alert_type == "LIVE_BROKER_KILL_SWITCH"
    assert intent.dedupe_key == "live-broker:kill-switch:service:armed"
    assert intent.payload["alert_key"] == "live-broker:kill-switch:service:armed"
    assert intent.payload["title"] == "live-broker kill switch armed"
    assert intent.payload["details"] == {"scope": "service"}
