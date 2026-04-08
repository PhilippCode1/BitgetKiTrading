from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from llm_orchestrator.exceptions import LLMPromptTooLargeError, RetryableLLMError


def test_settings_reject_fake_in_shadow(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("APP_ENV", "shadow")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    from llm_orchestrator.config import LLMOrchestratorSettings

    with pytest.raises(ValidationError) as ei:
        LLMOrchestratorSettings()
    assert "verboten" in str(ei.value)


def test_settings_reject_chat_fallback_in_shadow(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("APP_ENV", "shadow")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "false")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "false")
    monkeypatch.setenv("LLM_OPENAI_ALLOW_CHAT_FALLBACK", "true")
    from llm_orchestrator.config import LLMOrchestratorSettings

    with pytest.raises(ValidationError) as ei:
        LLMOrchestratorSettings()
    assert "LLM_OPENAI_ALLOW_CHAT_FALLBACK" in str(ei.value)


def test_retryable_exhaustion_raises_runtime_error(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    svc = LLMService(LLMOrchestratorSettings())
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }

    def always_timeout(*_a: object, **_k: object) -> dict:
        raise RetryableLLMError("upstream timeout", status_code=504)

    svc._fake.generate_structured = always_timeout  # type: ignore[method-assign]

    with patch("llm_orchestrator.service.sleep_backoff"):
        with pytest.raises(RuntimeError, match="upstream timeout"):
            svc.run_structured(
                schema_json=schema,
                prompt="p",
                temperature=0.0,
                provider_preference="auto",
            )


def test_schema_validation_failure_then_success(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ungueltige LLM-Antwort (wie fehlgeschlagene strukturierte Ausgabe) loest Retries aus."""
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "3")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    svc = LLMService(LLMOrchestratorSettings())
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }
    calls = {"n": 0}
    real = svc._fake.generate_structured

    def bad_then_ok(sch: dict, pr: str, **kw: object) -> dict:
        calls["n"] += 1
        if calls["n"] < 2:
            return {"wrong_key": True}
        return real(sch, pr, **kw)

    svc._fake.generate_structured = bad_then_ok  # type: ignore[method-assign]

    with patch("llm_orchestrator.service.sleep_backoff"):
        out = svc.run_structured(
            schema_json=schema, prompt="p", temperature=0.0, provider_preference="auto"
        )
    assert out["ok"] is True
    assert calls["n"] == 2


def test_prompt_too_large_service(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_PROMPT_CHARS", "300")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    svc = LLMService(LLMOrchestratorSettings())
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    with pytest.raises(LLMPromptTooLargeError):
        svc.run_structured(
            schema_json=schema,
            prompt="x" * 301,
            temperature=0.0,
        )


def test_prompt_too_large_http_413(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_PROMPT_CHARS", "300")
    from llm_orchestrator.app import create_app

    ikey = os.environ["INTERNAL_API_KEY"]
    client = TestClient(create_app(), headers={"X-Internal-Service-Key": ikey})
    body = {
        "schema_json": {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "prompt": "y" * 301,
        "temperature": 0.1,
    }
    r = client.post("/llm/structured", json=body)
    assert r.status_code == 413, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "PROMPT_TOO_LARGE"


def test_llm_unavailable_502_shape(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "1")
    from llm_orchestrator.app import create_app

    ikey = os.environ["INTERNAL_API_KEY"]
    client = TestClient(create_app(), headers={"X-Internal-Service-Key": ikey})

    from llm_orchestrator.service import LLMService

    svc: LLMService = client.app.state.service

    def boom(*_a: object, **_k: object) -> dict:
        raise RetryableLLMError("rate limited", status_code=429)

    svc._fake.generate_structured = boom  # type: ignore[method-assign]

    with patch("llm_orchestrator.service.sleep_backoff"):
        r = client.post(
            "/llm/structured",
            json={
                "schema_json": {
                    "type": "object",
                    "properties": {"a": {"type": "string"}},
                    "required": ["a"],
                },
                "prompt": "z",
                "temperature": 0.0,
            },
        )
    assert r.status_code == 502, r.text
    detail = r.json()["detail"]
    assert detail["code"] == "LLM_UNAVAILABLE"
    assert "rate limited" in detail["message"]
    assert detail.get("failure_class") == "retry_exhausted"


def test_llm_timeout_ms_validation_bounds(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_TIMEOUT_MS", "500")
    from llm_orchestrator.config import LLMOrchestratorSettings

    with pytest.raises(ValidationError):
        LLMOrchestratorSettings()
