from __future__ import annotations

import uuid

from shared_py.replay_determinism import (
    FLOAT_METRICS_RTOL,
    float_compare_metrics,
    normalized_timeframes,
    stable_decision_trace_id,
    stable_offline_backtest_run_id,
    stable_replay_session_id,
    stable_signal_row_id,
    stable_stream_event_id,
    trace_implies_replay_determinism,
)


def test_normalized_timeframes_order_and_dedup() -> None:
    assert normalized_timeframes(["5m", "1m", "5m"]) == ["1m", "5m"]
    # Gross/Kleinschreibung bleibt getrennt (DB-Paritaet); Reihenfolge stabil bei gleichem Sort-Key.
    assert normalized_timeframes(["1H", "1h"]) == ["1H", "1h"]


def test_stable_replay_session_id_invariant_under_timeframe_permutation() -> None:
    a = stable_replay_session_id(
        symbol="btcusdt",
        timeframes=["5m", "1m"],
        from_ts_ms=100,
        to_ts_ms=200,
        speed_factor=60.0,
        dedupe_prefix="replay",
        publish_ticks=False,
    )
    b = stable_replay_session_id(
        symbol="BTCUSDT",
        timeframes=["1m", "5m"],
        from_ts_ms=100,
        to_ts_ms=200,
        speed_factor=60.0,
        dedupe_prefix="replay",
        publish_ticks=False,
    )
    assert a == b
    assert a.version == 5


def test_stable_stream_event_id_uuid5_string() -> None:
    eid = stable_stream_event_id(stream="events:candle_close", dedupe_key="k1")
    uuid.UUID(eid)
    assert eid == stable_stream_event_id(stream="events:candle_close", dedupe_key="k1")
    assert eid != stable_stream_event_id(stream="events:candle_close", dedupe_key="k2")


def test_stable_offline_backtest_run_id_includes_seed_and_cv() -> None:
    base = stable_offline_backtest_run_id(
        symbol="BTCUSDT",
        timeframes=["5m"],
        from_ts_ms=1,
        to_ts_ms=2,
        cv_method="walk_forward",
        k_folds=5,
        embargo_pct=0.05,
        random_seed=42,
    )
    other_seed = stable_offline_backtest_run_id(
        symbol="BTCUSDT",
        timeframes=["5m"],
        from_ts_ms=1,
        to_ts_ms=2,
        cv_method="walk_forward",
        k_folds=5,
        embargo_pct=0.05,
        random_seed=43,
    )
    other_cv = stable_offline_backtest_run_id(
        symbol="BTCUSDT",
        timeframes=["5m"],
        from_ts_ms=1,
        to_ts_ms=2,
        cv_method="purged_kfold_embargo",
        k_folds=5,
        embargo_pct=0.05,
        random_seed=42,
    )
    assert base != other_seed
    assert base != other_cv


def test_trace_implies_replay() -> None:
    assert trace_implies_replay_determinism(
        {"source": "learning_engine.replay", "session_id": "x"}
    )
    assert trace_implies_replay_determinism({"determinism": {"replay_session_id": "s"}})
    assert not trace_implies_replay_determinism({"source": "market_stream"})
    assert not trace_implies_replay_determinism(None)


def test_stable_signal_row_id_idempotent() -> None:
    a = stable_signal_row_id(
        replay_session_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        upstream_event_id="evt-1",
        symbol="btcusdt",
        timeframe="5m",
        analysis_ts_ms=100,
        signal_output_schema_version="1.0",
    )
    b = stable_signal_row_id(
        replay_session_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        upstream_event_id="evt-1",
        symbol="BTCUSDT",
        timeframe="5m",
        analysis_ts_ms=100,
        signal_output_schema_version="1.0",
    )
    assert a == b


def test_stable_decision_trace_id() -> None:
    d1 = stable_decision_trace_id(signal_id="s1", decision_policy_version="hybrid-v4")
    d2 = stable_decision_trace_id(signal_id="s1", decision_policy_version="hybrid-v4")
    d3 = stable_decision_trace_id(signal_id="s2", decision_policy_version="hybrid-v4")
    assert d1 == d2
    assert d1 != d3


def test_float_compare_metrics_rtol() -> None:
    rtol = FLOAT_METRICS_RTOL
    assert float_compare_metrics({"x": 1.0}, {"x": 1.0 + 0.5 * rtol})
    assert not float_compare_metrics({"x": 1.0}, {"x": 1.0 + 50 * rtol})
    # int und float 1 sind in Python gleich — Schluessel muessen exakt passen.
    assert not float_compare_metrics({"x": 1.0}, {"y": 1.0}, rtol=rtol)
