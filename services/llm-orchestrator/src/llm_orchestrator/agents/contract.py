from __future__ import annotations

from functools import lru_cache
from typing import Any

from llm_orchestrator.paths import load_json_schema
from llm_orchestrator.validation.schema_validate import validate_against_schema


@lru_cache(maxsize=1)
def _agent_communication_schema() -> dict[str, Any]:
    return load_json_schema("agent_communication.schema.json")


def validate_agent_message(instance: dict[str, Any]) -> None:
    """Strikte Draft-2020-12-Validierung aller Agenten-Nachrichten."""
    validate_against_schema(_agent_communication_schema(), instance)
