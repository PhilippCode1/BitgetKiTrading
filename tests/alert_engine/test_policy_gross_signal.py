from __future__ import annotations

import time

from alert_engine.alerts.policies import evaluate_signal_created
from alert_engine.config import Settings

from shared_py.eventbus import EventEnvelope


def test_gross_class_triggers_gross_signal() -> None:
    s = Settings(
        alert_signal_gross_threshold=80,
        alert_signal_core_threshold=65,
        alert_dedupe_minutes_gross=10,
        alert_dedupe_minutes_core=10,
    )
    now = int(time.time() * 1000)
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="5m",
        payload={
            "signal_id": "x",
            "direction": "long",
            "signal_strength_0_100": 50,
            "probability_0_1": 0.5,
            "signal_class": "gross",
            "analysis_ts_ms": now,
            "reasons_json": ["a", "b", "c"],
        },
    )
    intents = evaluate_signal_created(env, s)
    assert len(intents) == 1
    assert intents[0].alert_type == "GROSS_SIGNAL"


def test_high_strength_triggers_gross() -> None:
    s = Settings(
        alert_signal_gross_threshold=80,
        alert_signal_core_threshold=65,
        alert_dedupe_minutes_gross=10,
        alert_dedupe_minutes_core=10,
    )
    now = int(time.time() * 1000)
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="1m",
        payload={
            "signal_id": "y",
            "direction": "short",
            "signal_strength_0_100": 85,
            "probability_0_1": 0.6,
            "signal_class": "mikro",
            "analysis_ts_ms": now,
            "reasons_json": [],
        },
    )
    intents = evaluate_signal_created(env, s)
    assert intents[0].alert_type == "GROSS_SIGNAL"


def test_core_only_when_below_gross_threshold() -> None:
    s = Settings(
        alert_signal_gross_threshold=80,
        alert_signal_core_threshold=65,
        alert_dedupe_minutes_gross=10,
        alert_dedupe_minutes_core=10,
    )
    now = int(time.time() * 1000)
    env = EventEnvelope(
        event_type="signal_created",
        symbol="BTCUSDT",
        timeframe="1m",
        payload={
            "signal_id": "z",
            "direction": "long",
            "signal_strength_0_100": 70,
            "probability_0_1": 0.55,
            "signal_class": "kern",
            "analysis_ts_ms": now,
            "reasons_json": [],
        },
    )
    intents = evaluate_signal_created(env, s)
    assert len(intents) == 1
    assert intents[0].alert_type == "CORE_SIGNAL"
