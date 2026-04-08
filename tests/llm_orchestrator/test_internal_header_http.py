from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_llm_post_401_without_internal_header_when_key_configured(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("INTERNAL_API_KEY", "orch-internal-key-for-unit-test-32")

    from llm_orchestrator.app import create_app

    client = TestClient(create_app())
    body = {
        "schema_json": {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "prompt": "x",
        "temperature": 0.0,
    }
    r = client.post("/llm/structured", json=body)
    assert r.status_code == 401, r.text
    assert r.json()["detail"]["code"] == "INTERNAL_AUTH_REQUIRED"


def test_llm_post_200_with_internal_header(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("INTERNAL_API_KEY", "orch-internal-key-for-unit-test-32")

    from llm_orchestrator.app import create_app

    client = TestClient(create_app())
    body = {
        "schema_json": {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "prompt": "x",
        "temperature": 0.0,
    }
    r = client.post(
        "/llm/structured",
        json=body,
        headers={"X-Internal-Service-Key": "orch-internal-key-for-unit-test-32"},
    )
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True
