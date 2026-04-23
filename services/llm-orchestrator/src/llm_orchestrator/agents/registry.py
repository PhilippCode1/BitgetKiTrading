from __future__ import annotations

from typing import Any, Callable, Iterable

from llm_orchestrator.agents.base import BaseTradingAgent


class AgentRegistry:
    """Registrierung und Discovery von Trading-Agenten (MARL-Grundgeruest)."""

    def __init__(self) -> None:
        self._by_id: dict[str, BaseTradingAgent] = {}

    def register(self, agent: BaseTradingAgent) -> None:
        if agent.agent_id in self._by_id:
            raise ValueError(f"Agent bereits registriert: {agent.agent_id}")
        self._by_id[agent.agent_id] = agent

    def unregister(self, agent_id: str) -> None:
        self._by_id.pop(agent_id, None)

    def get(self, agent_id: str) -> BaseTradingAgent:
        try:
            return self._by_id[agent_id]
        except KeyError as exc:
            raise KeyError(f"Unbekannter Agent: {agent_id}") from exc

    def list_ids(self) -> list[str]:
        return sorted(self._by_id)

    def all_agents(self) -> Iterable[BaseTradingAgent]:
        return list(self._by_id.values())

    @classmethod
    def build_default(
        cls,
        *,
        settings: Any | None = None,
        feature_engine_base_url: str = "http://127.0.0.1:8020",
        risk_settings: Any | None = None,
        macro_factory: Callable[..., BaseTradingAgent] | None = None,
        quant_factory: Callable[..., BaseTradingAgent] | None = None,
        risk_factory: Callable[..., BaseTradingAgent] | None = None,
    ) -> AgentRegistry:
        """Standard-Flotte: Macro, Quant, Risk (ohne automatische Verkabelung)."""
        from llm_orchestrator.agents.macro import MacroAnalystAgent
        from llm_orchestrator.agents.quant import QuantAnalystAgent
        from llm_orchestrator.agents.risk_governor import RiskGovernorAgent

        reg = cls()
        mf = macro_factory or MacroAnalystAgent
        qf = quant_factory or QuantAnalystAgent
        rf = risk_factory or RiskGovernorAgent
        reg.register(mf(settings=settings))
        reg.register(qf(feature_engine_base_url=feature_engine_base_url))
        reg.register(rf(risk_settings=risk_settings, llm_settings=settings))
        return reg
