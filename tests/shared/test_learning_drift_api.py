"""Tests fuer gemeinsame Learning-Drift-API-Huellen."""

from __future__ import annotations

from shared_py.learning_drift_api import (
    drift_recent_response,
    gateway_online_drift_state_response,
    learning_engine_online_drift_state_body,
)


def test_gateway_online_state_with_row() -> None:
    row = {
        "scope": "global",
        "effective_action": "warn",
        "computed_at": "2026-01-01T00:00:00+00:00",
        "lookback_minutes": 60,
        "breakdown_json": {"n": 1},
    }
    out = gateway_online_drift_state_response(row)
    assert out["status"] == "ok"
    assert out["item"] == row
    assert out["seeded"] is False


def test_learning_engine_online_state_empty_row() -> None:
    out = learning_engine_online_drift_state_body(None)
    assert out["status"] == "ok"
    assert out["scope"] == "global"
    assert out["effective_action"] == "ok"
    assert isinstance(out["breakdown_json"], dict)
    assert out["breakdown_json"].get("_meta", {}).get("empty") is True


def test_drift_recent_non_empty_no_seed_flag() -> None:
    items = [
        {
            "drift_id": "x",
            "metric_name": "m",
            "severity": "s",
            "details_json": {},
            "detected_ts": None,
        }
    ]
    out = drift_recent_response(items=items, limit=10)
    assert out["items"] == items
    assert out["seeded"] is False
    assert "seed_metadata" not in out


def test_gateway_online_state_empty_envelope() -> None:
    out = gateway_online_drift_state_response(None)
    assert out["status"] == "ok"
    assert out["item"] is None
    assert out.get("detail") is None
    if out.get("seed_metadata"):
        assert out["seeded"] is True
