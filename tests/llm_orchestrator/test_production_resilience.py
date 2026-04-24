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


def test_retryable_exhaustion_returns_graceful_degraded(
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
        out = svc.run_structured(
            schema_json=schema,
            prompt="p",
            temperature=0.0,
            provider_preference="auto",
        )
    assert out.get("orchestrator_status") == "degraded"
    assert out.get("llm_error_code") in (
        "LLM_ORCHESTRATOR_TIMEOUT",
        "LLM_UPSTREAM_FAILED",
    )
    assert out.get("ok") is True
    assert "result" in out


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


def test_llm_exhausted_graceful_200_degraded(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("orchestrator_status") == "degraded"
    assert body.get("llm_error_code") == "LLM_UPSTREAM_FAILED"
    assert body.get("ok") is True


def test_llm_timeout_ms_validation_bounds(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_TIMEOUT_MS", "500")
    from llm_orchestrator.config import LLMOrchestratorSettings

    with pytest.raises(ValidationError):
        LLMOrchestratorSettings()


def test_json_self_repair_triggers_and_returns_valid_json(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    DoD: ungueltige erste Ausgabe (fehlendes Pflichtfeld) -> Reparatur-Prompt mit
    \"Das JSON ist ungültig\" -> zweite Ausgabe schema-konform.
    """
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "2")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    svc = LLMService(LLMOrchestratorSettings())
    schema = {
        "type": "object",
        "required": ["a", "b"],
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "integer"},
        },
        "additionalProperties": False,
    }
    prompts: list[str] = []

    def first_bad_then_repaired(s: dict, pr: str, **kw: object) -> dict:
        prompts.append(str(pr))
        if len(prompts) == 1:
            return {"a": "truncated-sim"}  # fehlt b — wie abgeschnittener/kaputter Output
        return {"a": "repaired", "b": 0}

    svc._fake.generate_structured = first_bad_then_repaired  # type: ignore[method-assign]
    with patch("llm_orchestrator.service.sleep_backoff"):
        out = svc.run_structured(
            schema_json=schema, prompt="bitte b ausgeben", temperature=0.0
        )
    assert out.get("ok") is True
    res = out.get("result")
    assert isinstance(res, dict)
    assert res.get("a") == "repaired" and res.get("b") == 0
    assert len(prompts) == 2, "Erwartet: Primaer + ein Selbstreparatur-Call"
    assert "Das JSON ist ungültig" in prompts[1]
    assert "Fehler:" in prompts[1]
    from llm_orchestrator.validation.schema_validate import validate_against_schema

    validate_against_schema(schema, res)


def test_circuit_opens_after_three_degraded_events(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-circuit")
    monkeypatch.setenv("LLM_CIRCUIT_FAIL_THRESHOLD", "3")
    monkeypatch.setenv("LLM_CIRCUIT_WINDOW_SEC", "60")
    settings = LLMOrchestratorSettings()
    assert settings.llm_circuit_fail_threshold == 3
    assert settings.llm_circuit_window_sec == 60

    svc = LLMService(settings)
    for _ in range(2):
        svc._circuit.record_upstream_degraded("openai")
    assert not svc._circuit.is_open("openai")
    svc._circuit.record_upstream_degraded("openai")
    assert svc._circuit.is_open("openai")

    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }
    out = svc.run_structured(
        schema_json=schema, prompt="p", temperature=0.0, provider_preference="auto"
    )
    assert out.get("orchestrator_status") == "degraded"
    assert out.get("llm_error_code") == "LLM_PROVIDER_OFFLINE"
    out2 = svc.run_structured(
        schema_json=schema, prompt="p", temperature=0.0, provider_preference="auto"
    )
    assert out2.get("orchestrator_status") == "degraded"
    assert out2.get("llm_error_code") == "LLM_PROVIDER_OFFLINE"
