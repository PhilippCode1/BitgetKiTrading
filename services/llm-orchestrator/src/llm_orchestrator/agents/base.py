from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from llm_orchestrator.agents.contract import validate_agent_message


class BaseTradingAgent(ABC):
    """Abstrakte Basis: Analyse entkoppelt von Ausführung; Ausgabe immer schema-valide."""

    agent_id: str

    def __init__(self, *, agent_id: str) -> None:
        if not agent_id or not str(agent_id).strip():
            raise ValueError("agent_id darf nicht leer sein")
        self.agent_id = str(agent_id).strip()
        self._last_confidence: float = 0.0

    def _finalize(self, message: dict[str, Any]) -> dict[str, Any]:
        if message.get("agent_id") != self.agent_id:
            raise ValueError("agent_id in Nachricht muss Agent.agent_id entsprechen")
        validate_agent_message(message)
        try:
            self._last_confidence = float(message["confidence_0_1"])
        except (KeyError, TypeError, ValueError):
            self._last_confidence = 0.0
        return message

    @abstractmethod
    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Erzeugt eine vollständige Agent-Nachricht (JSON-Objekt, schema-valide)."""

    async def get_confidence_score(self) -> float:
        """Letzte Konfidenz nach erfolgreichem ``analyze`` (sonst 0.0)."""
        return float(self._last_confidence)
