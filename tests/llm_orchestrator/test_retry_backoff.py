from __future__ import annotations

from unittest.mock import patch

import pytest
from llm_orchestrator.exceptions import RetryableLLMError
from llm_orchestrator.constants import LLM_ORCHESTRATOR_API_CONTRACT_VERSION
from llm_orchestrator.retry.backoff import sleep_backoff


def test_llm_service_health_includes_api_contract_and_backoff_note(
    mock_redis_bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    h = LLMService(LLMOrchestratorSettings()).health()
    assert h["api_contract_version"] == LLM_ORCHESTRATOR_API_CONTRACT_VERSION
    assert "backoff_sleep_determinism" in h
    assert "LLM_BACKOFF_JITTER_RATIO=0" in h["backoff_sleep_determinism"]


def test_sleep_backoff_jitter_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "llm_orchestrator.retry.backoff.time.sleep", lambda s: sleeps.append(float(s))
    )
    sleep_backoff(2, base_sec=1.0, max_sec=10.0, jitter_ratio=0.2)
    # exp = min(10, 1*4) = 4; jitter = 4 * 0.2 * 0.5 = 0.4
    assert sleeps == [4.4]


def test_sleep_backoff_invokes_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(
        "llm_orchestrator.retry.backoff.time.sleep", lambda s: sleeps.append(float(s))
    )
    sleep_backoff(0, base_sec=0.01, max_sec=1.0, jitter_ratio=0.0)
    sleep_backoff(1, base_sec=0.01, max_sec=1.0, jitter_ratio=0.0)
    assert len(sleeps) == 2
    assert sleeps[1] >= sleeps[0]


def test_fake_provider_retries_on_retryable(mock_redis_bus, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("LLM_USE_FAKE_PROVIDER", "true")
    monkeypatch.setenv("LLM_MAX_RETRIES", "4")
    from llm_orchestrator.config import LLMOrchestratorSettings
    from llm_orchestrator.service import LLMService

    svc = LLMService(LLMOrchestratorSettings())
    schema = {
        "type": "object",
        "properties": {"z": {"type": "string"}},
        "required": ["z"],
    }
    calls = {"n": 0}
    real = svc._fake.generate_structured

    def flaky(sch: dict, pr: str, **kw: object) -> dict:
        calls["n"] += 1
        if calls["n"] < 2:
            raise RetryableLLMError("429", status_code=429)
        return real(sch, pr, **kw)

    svc._fake.generate_structured = flaky  # type: ignore[method-assign]

    with patch("llm_orchestrator.service.sleep_backoff"):
        out = svc.run_structured(
            schema_json=schema, prompt="p", temperature=0.0, provider_preference="auto"
        )
    assert out["ok"] is True
    assert calls["n"] == 2
