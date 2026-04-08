from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared_py.eventbus import (
    ENVELOPE_FINGERPRINT_CANON_VERSION,
    STREAM_CANDLE_CLOSE,
    EventEnvelope,
    envelope_fingerprint_preimage,
    envelope_fingerprint_sha256,
    stable_json_dumps,
)
from shared_py.replay_determinism import stable_stream_event_id

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "contracts"
CANDLE_FIXTURE = FIXTURES / "envelope_candle_close_ok.json"


def _read_golden(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8").strip().split()[0]


def test_semantic_fingerprint_matches_golden() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    assert envelope_fingerprint_sha256(env, mode="semantic") == _read_golden(
        "envelope_candle_close_ok.semantic.sha256"
    )


def test_wire_fingerprint_matches_golden() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    assert envelope_fingerprint_sha256(env, mode="wire") == _read_golden(
        "envelope_candle_close_ok.wire.sha256"
    )


def test_payload_key_order_invariant_semantic_hash() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    data = env.model_dump(mode="json", exclude_none=False)
    payload = data["payload"]
    assert isinstance(payload, dict)
    keys = sorted(payload.keys(), reverse=True)
    shuffled = {k: payload[k] for k in keys}
    data2 = {**data, "payload": shuffled}
    env2 = EventEnvelope.model_validate(data2)
    assert envelope_fingerprint_sha256(env, mode="semantic") == envelope_fingerprint_sha256(
        env2, mode="semantic"
    )


def test_roundtrip_json_stable_preimage() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    pre = envelope_fingerprint_preimage(env, mode="semantic")
    s1 = stable_json_dumps(pre)
    pre2 = json.loads(s1)
    s2 = stable_json_dumps(pre2)
    assert s1 == s2


def test_semantic_excludes_event_id_and_ingest() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    pre = envelope_fingerprint_preimage(env, mode="semantic")
    blob = stable_json_dumps(pre)
    assert "ingest_ts_ms" not in blob
    assert "550e8400-e29b-41d4-a716-446655440000" not in blob


def test_wire_includes_event_id() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    pre = envelope_fingerprint_preimage(env, mode="wire")
    blob = stable_json_dumps(pre)
    assert "550e8400-e29b-41d4-a716-446655440000" in blob
    assert "ingest_ts_ms" in blob


def test_replay_trace_stabilizes_event_id_and_ingest_from_dedupe_key() -> None:
    dk = "unit:replay:BTCUSDT:1m:1700000000000"
    ex_ms = 1700000000060
    trace = {
        "source": "learning_engine.replay",
        "determinism": {"replay_session_id": "00000000-0000-5000-8000-000000000001"},
    }
    env_a = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        timeframe="1m",
        exchange_ts_ms=ex_ms,
        dedupe_key=dk,
        payload={"close": "1"},
        trace=trace,
    )
    env_b = EventEnvelope(
        event_type="candle_close",
        symbol="BTCUSDT",
        timeframe="1m",
        exchange_ts_ms=ex_ms,
        dedupe_key=dk,
        payload={"close": "1"},
        trace=trace,
    )
    want_id = stable_stream_event_id(stream=STREAM_CANDLE_CLOSE, dedupe_key=dk)
    assert env_a.event_id == want_id
    assert env_b.event_id == want_id
    assert env_a.ingest_ts_ms == ex_ms
    assert env_b.ingest_ts_ms == ex_ms


def test_non_replay_fixture_trace_unchanged_ids() -> None:
    env = EventEnvelope.model_validate_json(CANDLE_FIXTURE.read_text(encoding="utf-8"))
    assert env.event_id == "550e8400-e29b-41d4-a716-446655440000"
    assert env.ingest_ts_ms == 1700000000100


@pytest.mark.parametrize(
    "path",
    [
        REPO_ROOT / "shared" / "ts" / "src" / "contractVersions.ts",
    ],
)
def test_ts_contract_versions_match_catalog(path: Path) -> None:
    catalog = json.loads(
        (REPO_ROOT / "shared" / "contracts" / "catalog" / "event_streams.json").read_text(
            encoding="utf-8"
        )
    )
    text = path.read_text(encoding="utf-8")
    assert catalog["envelope_default_schema_version"] in text
    assert str(catalog["envelope_fingerprint_canon_version"]) in text
    assert ENVELOPE_FINGERPRINT_CANON_VERSION == str(catalog["envelope_fingerprint_canon_version"])
