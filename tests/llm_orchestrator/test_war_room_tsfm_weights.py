from __future__ import annotations

import asyncio
import copy
from typing import Any

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.registry import AgentRegistry
from llm_orchestrator.consensus.war_room import (
    QUANT_ID,
    ConsensusOrchestrator,
    _consensus_weight_vector,
)


def _msg(
    *,
    agent_id: str,
    action: str,
    conf: float,
    rationale: str,
    payload: dict[str, Any] | None = None,
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
            "payload": payload or {},
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


def test_quant_weight_boost_when_tsfm_confidence_high() -> None:
    base = {"macro_analyst": 0.28, "quant_analyst": 0.47, "risk_governor": 0.25}
    quant_m = _msg(
        agent_id="quant_analyst",
        action="buy_bias",
        conf=0.9,
        rationale="x",
        payload={
            "tsfm_primary_source": True,
            "tsfm_model_confidence_0_1": 0.95,
            "tsfm_directional_bias": "long",
        },
    )
    wn, w0, weff = _consensus_weight_vector(base, quant_m)
    assert wn[QUANT_ID] > w0 / sum(base.values()) * 0.99


def test_news_shock_downgrades_tsfm_long_consensus_confidence() -> None:
    reg = AgentRegistry()
    reg.register(
        StubAgent(
            "macro_analyst",
            _msg(
                agent_id="macro_analyst",
                action="hold_research",
                conf=0.5,
                rationale="m",
                payload={"news_shock": True},
            ),
        )
    )
    reg.register(
        StubAgent(
            "quant_analyst",
            _msg(
                agent_id="quant_analyst",
                action="buy_bias",
                conf=0.92,
                rationale="q",
                payload={
                    "tsfm_primary_source": True,
                    "tsfm_model_confidence_0_1": 0.95,
                    "tsfm_directional_bias": "long",
                },
            ),
        )
    )
    reg.register(
        StubAgent(
            "risk_governor",
            _msg(agent_id="risk_governor", action="allow", conf=0.8, rationale="r"),
        )
    )
    orch = ConsensusOrchestrator(reg)
    out = asyncio.run(
        orch.evaluate(
            {"news_context": {"news_shock": True}},
            agent_timeout_sec=5.0,
        )
    )
    audit = out["foundation_model_audit"]
    assert audit["shock_penalty_applied"] is True
    assert audit["quant_confidence_for_consensus_0_1"] < audit["quant_confidence_original_0_1"]
    assert "Cross-Check" in out["operator_explain"]["explanation_de"]
