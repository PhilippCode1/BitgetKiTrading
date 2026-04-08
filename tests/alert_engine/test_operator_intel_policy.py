from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ALERT_ENGINE_SRC = ROOT / "services" / "alert-engine" / "src"
for candidate in (ROOT / "shared" / "python" / "src", ALERT_ENGINE_SRC):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from alert_engine.alerts.policies import evaluate_operator_intel
from alert_engine.config import Settings
from shared_py.eventbus import EventEnvelope


class _FakeRedis:
    """Wie redis-py mit decode_responses=True (get liefert str)."""

    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = mapping

    def get(self, key: str) -> str | None:
        return self._m.get(key)


def test_operator_intel_maps_kind_and_reply_from_redis() -> None:
    settings = Settings.model_construct()
    env = EventEnvelope(
        event_type="operator_intel",
        symbol="BTCUSDT",
        payload={
            "intel_kind": "plan_summary",
            "severity": "info",
            "text": "plan ok",
            "correlation_id": "exec:42",
            "dedupe_key": "op:exec:42:plan",
            "dedupe_ttl_minutes": 30,
        },
    )
    r = _FakeRedis({"ae:opintel:thread:exec:42": "999"})
    intents = evaluate_operator_intel(env, settings, r)
    assert len(intents) == 1
    it = intents[0]
    assert it.alert_type == "OPERATOR_PLAN_SUMMARY"
    assert it.dedupe_key == "op:exec:42:plan"
    assert it.payload.get("reply_to_telegram_message_id") == 999


def test_operator_intel_pre_trade_maps_alert_type() -> None:
    settings = Settings.model_construct()
    env = EventEnvelope(
        event_type="operator_intel",
        symbol="BTCUSDT",
        payload={
            "intel_kind": "pre_trade_rationale",
            "severity": "info",
            "symbol": "BTCUSDT",
        },
    )
    intents = evaluate_operator_intel(env, settings, None)
    assert len(intents) == 1
    assert intents[0].alert_type == "OPERATOR_PRE_TRADE"
