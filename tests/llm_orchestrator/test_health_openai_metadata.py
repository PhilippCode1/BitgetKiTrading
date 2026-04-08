from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> TestClient:
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


def test_health_contains_openai_block(client: TestClient) -> None:
    r = client.get("/health", headers={"X-Request-ID": "health-probe-1"})
    assert r.status_code == 200, r.text
    body = r.json()
    oa = body.get("openai")
    assert isinstance(oa, dict)
    assert oa.get("structured_transport") in (
        "unavailable",
        "responses",
        "chat_completions",
    )
    models = oa.get("models")
    assert isinstance(models, dict)
    assert "OPENAI_MODEL_PRIMARY" in models
    assert "OPENAI_MODEL_HIGH_REASONING" in models
    assert "OPENAI_MODEL_FAST" in models
    assert body.get("provider_mode") == "fake"
    assert "structured_output" in body
    assert body["structured_output"].get("llm_timeout_ms", 0) >= 1000
    assert "providers_currently_open" in body.get("circuit", {})
    assert body.get("redis", {}).get("ok") is True
    assert body.get("last_structured_failure") is None
