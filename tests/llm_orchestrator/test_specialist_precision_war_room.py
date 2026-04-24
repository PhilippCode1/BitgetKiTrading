from __future__ import annotations

import asyncio
import copy
import logging
from typing import Any

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.registry import AgentRegistry
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.consensus.specialist_precision import (
    apply_precision_to_weights,
    precision_0_1_by_agent,
    precision_stake_multiplier,
)
from llm_orchestrator.consensus.war_room import ConsensusOrchestrator


def test_precision_stake_multiplier_thresholds() -> None:
    assert precision_stake_multiplier(0.71) == 1.5
    assert precision_stake_multiplier(0.50) == 1.0
    assert precision_stake_multiplier(0.49) == 0.5
    assert precision_stake_multiplier(0.60) == 1.0


def test_apply_precision_changes_relative_weights() -> None:
    base = {
        "macro_analyst": 0.28,
        "quant_analyst": 0.47,
        "risk_governor": 0.25,
    }
    # hohe Quant-Präzision -> 1.5x
    p = {
        "macro_analyst": 0.60,
        "quant_analyst": 0.75,
        "risk_governor": 0.40,
    }
    w = apply_precision_to_weights(base, p)
    assert w["quant_analyst"] > w["macro_analyst"]


def test_precision_0_1_by_agent_defaults() -> None:
    m = precision_0_1_by_agent({"specialists": {}})
    assert m["macro_analyst"] == 0.6
    assert m["quant_analyst"] == 0.6


def _msg(
    *,
    agent_id: str,
    action: str,
    conf: float,
    rationale: str,
) -> dict[str, Any]:
    return {
        "schema_version": "agent-comm-v1",
        "agent_id": agent_id,
        "status": "ok",
        "confidence_0_1": conf,
        "rationale_de": rationale,
        "signal_proposal": {
            "action": action,
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "payload": {},
        },
        "evidence_refs": [],
    }


class StubAgent(BaseTradingAgent):
    def __init__(self, agent_id: str, template: dict[str, Any]) -> None:
        super().__init__(agent_id=agent_id)
        self._template = template

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        del context
        m = copy.deepcopy(self._template)
        m["agent_id"] = self.agent_id
        return self._finalize(m)


def test_war_room_emits_weighted_stakes_log(caplog: object) -> None:
    reg = AgentRegistry()
    reg.register(StubAgent("macro_analyst", _msg(agent_id="macro_analyst", action="buy_bias", conf=0.8, rationale="m")))
    reg.register(StubAgent("quant_analyst", _msg(agent_id="quant_analyst", action="buy_bias", conf=0.8, rationale="q")))
    reg.register(StubAgent("risk_governor", _msg(agent_id="risk_governor", action="allow", conf=0.8, rationale="r")))
    s = LLMOrchestratorSettings()
    s.war_room_fetch_specialist_precision = False
    orch = ConsensusOrchestrator(reg, settings=s)
    with caplog.at_level(logging.INFO, logger="llm_orchestrator.consensus.specialist_precision"):
        asyncio.run(orch.evaluate({}, agent_timeout_sec=5.0))
    text = caplog.text
    assert "weighted_stakes pre_consensus" in text
    assert "macro_analyst" in text
    assert "quant_analyst" in text
    assert "risk_governor" in text


def test_veto_with_quant_directional_adds_readiness_line() -> None:
    reg = AgentRegistry()
    reg.register(StubAgent("macro_analyst", _msg(agent_id="macro_analyst", action="buy_bias", conf=0.8, rationale="m")))
    reg.register(StubAgent("quant_analyst", _msg(agent_id="quant_analyst", action="buy_bias", conf=0.85, rationale="q")))
    reg.register(
        StubAgent(
            "risk_governor",
            _msg(agent_id="risk_governor", action="veto", conf=0.95, rationale="r"),
        )
    )
    s = LLMOrchestratorSettings()
    s.war_room_fetch_specialist_precision = False
    orch = ConsensusOrchestrator(reg, settings=s)
    out = asyncio.run(orch.evaluate({}, agent_timeout_sec=5.0))
    ex = out["operator_explain"]["explanation_de"]
    assert "Readiness (konservativ)" in ex
    assert "do_not_trade" in ex
