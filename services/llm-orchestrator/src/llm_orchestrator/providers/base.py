from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    """Ein LLM-Backend mit Structured Output.

    Kein Tool-/Function-Calling: keine Orderhoheit, keine versteckten Nebenpfade.
    Erweiterungen gehen als neue explizite Methoden oder neue API-Version
    (``LLM_ORCHESTRATOR_API_CONTRACT_VERSION``), nicht als generisches ``call_tools``.
    """

    name: str
    default_model: str

    def generate_structured(
        self,
        schema_json: dict[str, Any],
        prompt: str,
        *,
        temperature: float,
        timeout_ms: int,
        model: str | None = None,
        system_instructions_de: str | None = None,
    ) -> dict[str, Any]: ...
