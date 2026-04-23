from __future__ import annotations


class LLMPromptTooLargeError(ValueError):
    """Eingabe-Prompt uebersteigt LLM_MAX_PROMPT_CHARS (Abwehr gegen Missbrauch)."""


class RetryableLLMError(Exception):
    """429/5xx oder transient — Backoff und erneuter Versuch."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMProviderOfflineError(Exception):
    """
    OpenAI-Circuit OPEN: sofort 503/Detail fuer BFF (i18n message_key).
    """

    def to_http_detail(self) -> dict[str, str]:
        return {
            "code": "LLM_PROVIDER_OFFLINE",
            "message_key": "llm.error.provider_offline",
        }


class GuardrailViolation(ValueError):
    """Modell-Output besteht Schema, verletzt aber Governance (Policy / Leak-Heuristik)."""

    def __init__(self, message: str, *, codes: list[str]) -> None:
        super().__init__(message)
        self.codes = codes
