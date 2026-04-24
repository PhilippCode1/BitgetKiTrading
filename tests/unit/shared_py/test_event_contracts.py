from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

from shared_py.eventbus import (
    ENVELOPE_DEFAULT_SCHEMA_VERSION,
    ENVELOPE_FINGERPRINT_CANON_VERSION,
    EVENT_STREAMS,
    LIVE_SSE_STREAMS,
    EventEnvelope,
    EventType,
    SchemaValidationError,
    event_stream_for_type,
)
from shared_py.eventbus.envelope import EVENT_TYPE_TO_STREAM

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "shared" / "contracts"
CATALOG = CONTRACTS / "catalog" / "event_streams.json"
SCHEMAS = CONTRACTS / "schemas"


def _contract_registry() -> tuple[Registry, dict]:
    r = Registry()
    for f in sorted(SCHEMAS.glob("*.schema.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        key = str(doc.get("$id", f"https://bitget-btc-ai.local/schemas/{f.name}"))
        r = r.with_resource(
            key,
            Resource.from_contents(doc, default_specification=DRAFT202012),
        )
    env = json.loads((SCHEMAS / "event_envelope.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(env, registry=r)
    Draft202012Validator.check_schema(v.schema)
    return r, env


def test_catalog_file_matches_runtime() -> None:
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = raw["streams"]
    assert {r["event_type"]: r["stream"] for r in rows} == EVENT_TYPE_TO_STREAM
    assert tuple(r["stream"] for r in rows) == EVENT_STREAMS
    assert tuple(raw["live_sse_streams"]) == LIVE_SSE_STREAMS
    assert raw["envelope_default_schema_version"] == ENVELOPE_DEFAULT_SCHEMA_VERSION
    assert raw["envelope_fingerprint_canon_version"] == ENVELOPE_FINGERPRINT_CANON_VERSION


def test_event_type_literal_matches_catalog() -> None:
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    types_in_json = {r["event_type"] for r in raw["streams"]}
    assert types_in_json == set(get_args(EventType))


def test_live_sse_subset_of_all_streams() -> None:
    for s in LIVE_SSE_STREAMS:
        assert s in EVENT_STREAMS


def test_event_envelope_schema_enum_matches_catalog() -> None:
    schema_path = CONTRACTS / "schemas" / "event_envelope.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    a = schema.get("allOf", [])
    base: dict
    if isinstance(a, list) and a and isinstance(a[0], dict) and a[0].get("type") == "object":
        base = a[0]
    else:
        base = schema
    enum_vals = set((base.get("properties") or {}).get("event_type", {}).get("enum", ()))
    raw = json.loads(CATALOG.read_text(encoding="utf-8"))
    assert enum_vals == {r["event_type"] for r in raw["streams"]}


def test_fixture_envelope_passes_jsonschema() -> None:
    r, env = _contract_registry()
    instance = json.loads(
        (REPO_ROOT / "tests" / "fixtures" / "contracts" / "envelope_candle_close_ok.json").read_text(
            encoding="utf-8"
        )
    )
    v = Draft202012Validator(env, registry=r)
    assert list(v.iter_errors(instance)) == []


def test_candle_close_payload_wrong_type_raises() -> None:
    with pytest.raises(SchemaValidationError) as e:
        bad_close: object = "sollte_zahl_sein"
        EventEnvelope(
            event_type="candle_close",
            symbol="BTCUSDT",
            payload={
                "start_ts_ms": 1,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": bad_close,
            },
        )
    assert "number" in str(e.value).lower()


def test_ensure_payload_matches_schema_wrong_type_raises() -> None:
    from shared_py.eventbus import ensure_payload_matches_schema

    with pytest.raises(SchemaValidationError):
        ensure_payload_matches_schema(
            "candle_close",
            {
                "start_ts_ms": 1,
                "open": 1.0,
                "high": 1.0,
                "low": 1.0,
                "close": "keine_zahl",
            },
        )


def test_fixture_envelope_pydantic_roundtrip() -> None:
    path = REPO_ROOT / "tests" / "fixtures" / "contracts" / "envelope_candle_close_ok.json"
    env = EventEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
    assert env.event_type == "candle_close"
    assert env.default_stream() == event_stream_for_type("candle_close")


@pytest.mark.parametrize(
    ("payload_schema", "event_type"),
    [
        ("payload_candle_close.schema.json", "candle_close"),
        ("payload_signal_created.schema.json", "signal_created"),
        ("payload_market_feed_health.schema.json", "market_feed_health"),
    ],
)
def test_payload_schemas_minimal(payload_schema: str, event_type: EventType) -> None:
    schema = json.loads((CONTRACTS / "schemas" / payload_schema).read_text(encoding="utf-8"))
    env = EventEnvelope(
        event_type=event_type,
        payload=_minimal_payload(event_type),
        trace={},
    )
    data = env.model_dump(mode="json")
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)
    errs = list(v.iter_errors(data["payload"]))
    assert errs == [], [e.message for e in errs]


def _minimal_payload(event_type: EventType) -> dict:
    if event_type == "candle_close":
        return {
            "start_ts_ms": 1,
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
        }
    if event_type == "signal_created":
        return {"signal_id": "s1", "direction": "long"}
    if event_type == "market_feed_health":
        return {
            "ok": True,
            "ws_connected": True,
            "symbol": "BTCUSDT",
            "reasons": [],
            "ready_max_age_ms": 180_000,
            "orderbook_desynced": False,
            "stale_escalation_count": 0,
        }
    raise AssertionError(event_type)
