from __future__ import annotations

from monitor_engine.checks.redis_streams import (
    compute_heuristic_lag,
    parse_stream_id_ms,
)


def test_parse_stream_id_ms() -> None:
    assert parse_stream_id_ms("1730000000000-0") == 1730000000000
    assert parse_stream_id_ms("0-0") is None
    assert parse_stream_id_ms(None) is None


def test_compute_heuristic_lag_prefers_redis() -> None:
    assert (
        compute_heuristic_lag(
            redis_lag=42,
            last_generated_id="100-0",
            last_delivered_id="50-0",
        )
        == 42
    )


def test_compute_heuristic_lag_fallback_ids() -> None:
    assert (
        compute_heuristic_lag(
            redis_lag=None,
            last_generated_id="200-0",
            last_delivered_id="100-0",
        )
        == 100
    )
