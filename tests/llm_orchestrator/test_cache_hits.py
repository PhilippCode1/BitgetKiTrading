from __future__ import annotations

import json

import pytest
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.service import LLMService


def test_cache_second_call_uses_redis(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_CACHE_TTL_SEC", "3600")
    svc = LLMService(LLMOrchestratorSettings())
    schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }
    a = svc.run_structured(schema_json=schema, prompt="same", temperature=0.1)
    b = svc.run_structured(schema_json=schema, prompt="same", temperature=0.1)
    assert a["cached"] is False
    assert b["cached"] is True
    assert a["result"] == b["result"]
    store = mock_redis_bus["store"]
    assert len(store) >= 1
    first_key = next(iter(store))
    assert json.loads(store[first_key]) == a["result"]
