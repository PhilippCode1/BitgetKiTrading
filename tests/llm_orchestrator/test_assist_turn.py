from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from shared_py.llm_assist_context import filter_assist_context_payload


def test_filter_assist_context_strips_unknown_keys() -> None:
    raw = {
        "platform_health": {"ok": True},
        "evil_foreign_tenant_dump": {"x": 1},
    }
    out = filter_assist_context_payload("admin_operations", raw)
    assert "platform_health" in out
    assert "evil_foreign_tenant_dump" not in out


def test_filter_assist_context_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="unknown_assist_role"):
        filter_assist_context_payload("not_a_real_role", {})


@pytest.fixture
def client(mock_redis_bus, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    monkeypatch.setenv("API_GATEWAY_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("NEXT_PUBLIC_WS_BASE_URL", "ws://127.0.0.1:8000")
    from llm_orchestrator.app import create_app

    ikey = os.environ.get("INTERNAL_API_KEY", "").strip()
    hdrs = {"X-Internal-Service-Key": ikey} if ikey else {}
    return TestClient(create_app(), headers=hdrs)


def test_assist_turn_roundtrip_and_history(client: TestClient, mock_redis_bus: dict) -> None:
    conv = str(uuid.uuid4())
    body = {
        "assist_role": "admin_operations",
        "conversation_id": conv,
        "tenant_partition_id": "test-partition",
        "user_message_de": "Was ist ein Live-Gate?",
        "context_json": {"platform_health": {"status": "ok"}},
    }
    r = client.post("/llm/assist/turn", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["provider"] == "fake"
    assert data["provenance"]["task_type"] == "admin_operations_assist"
    sess = data.get("assist_session") or {}
    assert sess.get("conversation_id") == conv
    assert sess.get("history_message_count") == 2

    store = mock_redis_bus["store"]
    keys = [k for k in store if conv in k]
    assert keys, "conversation should be stored in redis mock"
    hist = json.loads(store[keys[0]])
    assert len(hist) == 2
    assert hist[0]["role"] == "user"
    assert hist[1]["role"] == "assistant"


def test_assist_roles_do_not_share_redis_history(
    client: TestClient, mock_redis_bus: dict
) -> None:
    conv = str(uuid.uuid4())
    part = "same-partition-test"
    r1 = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "admin_operations",
            "conversation_id": conv,
            "tenant_partition_id": part,
            "user_message_de": "Admin frage eins?",
            "context_json": {"platform_health": {"status": "ok"}},
        },
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        "/llm/assist/turn",
        json={
            "assist_role": "strategy_signal",
            "conversation_id": conv,
            "tenant_partition_id": part,
            "user_message_de": "Signal frage eins?",
            "context_json": {"signal_snapshot": {"id": "s1"}},
        },
    )
    assert r2.status_code == 200, r2.text
    data2 = r2.json()
    assert data2["assist_session"]["history_message_count"] == 2

    store = mock_redis_bus["store"]
    keys = [k for k in store if conv in k]
    assert len(keys) == 2
    assert any("admin_operations" in k for k in keys)
    assert any("strategy_signal" in k for k in keys)


def test_assist_turn_accumulates_history(client: TestClient) -> None:
    conv = str(uuid.uuid4())
    part = "p2"
    for i, msg in enumerate(("Erste Frage zum Gate", "Zweite Nachfrage", "Dritte Nachfrage")):
        r = client.post(
            "/llm/assist/turn",
            json={
                "assist_role": "strategy_signal",
                "conversation_id": conv,
                "tenant_partition_id": part,
                "user_message_de": msg,
                "context_json": {"signal_snapshot": {"id": "s1"}},
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["assist_session"]["history_message_count"] == 2 * (i + 1)
