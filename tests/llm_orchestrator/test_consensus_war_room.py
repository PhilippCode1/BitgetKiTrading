from __future__ import annotations

import asyncio
import copy
from typing import Any

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.registry import AgentRegistry
from llm_orchestrator.consensus.war_room import ConsensusOrchestrator
from llm_orchestrator.paths import load_json_schema
from llm_orchestrator.validation.schema_validate import validate_against_schema


def _msg(
    *,
    agent_id: str,
    action: str,
    conf: float,
    rationale: str,
    status: str = "ok",
) -> dict[str, Any]:
    return {
        "schema_version": "agent-comm-v1",
        "agent_id": agent_id,
        "status": status,
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


def test_risk_veto_aborts_signal_generation() -> None:
    reg = AgentRegistry()
    reg.register(
        StubAgent(
            "macro_analyst",
            _msg(
                agent_id="macro_analyst",
                action="buy_bias",
                conf=0.9,
                rationale="Makro: News unterstuetzen Long.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "quant_analyst",
            _msg(
                agent_id="quant_analyst",
                action="buy_bias",
                conf=0.85,
                rationale="Quant: RSI niedrig, Long-Bias.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "risk_governor",
            _msg(
                agent_id="risk_governor",
                action="veto",
                conf=0.95,
                rationale="Risk: harte Sperre / do_not_trade.",
            ),
        )
    )
    orch = ConsensusOrchestrator(reg, weights=None)
    out = asyncio.run(orch.evaluate({}, agent_timeout_sec=5.0))
    assert out["risk_hard_veto"] is True
    assert out["signal_generation_aborted"] is True
    assert out["final_signal_action"] == "none"
    assert out["consensus_status"] == "veto_aborted"
    validate_against_schema(load_json_schema("operator_explain.schema.json"), out["operator_explain"])
    assert "Hard-Veto" in out["operator_explain"]["explanation_de"]


def test_macro_quant_divergence_marks_high_uncertainty() -> None:
    reg = AgentRegistry()
    reg.register(
        StubAgent(
            "macro_analyst",
            _msg(
                agent_id="macro_analyst",
                action="sell_bias",
                conf=0.8,
                rationale="Makro: Risikoaversion.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "quant_analyst",
            _msg(
                agent_id="quant_analyst",
                action="buy_bias",
                conf=0.82,
                rationale="Quant: technischer Long-Bias.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "risk_governor",
            _msg(
                agent_id="risk_governor",
                action="allow",
                conf=0.7,
                rationale="Risk: keine universellen Hard-Blocks.",
            ),
        )
    )
    orch = ConsensusOrchestrator(reg)
    out = asyncio.run(orch.evaluate({}))
    assert out["macro_quant_high_uncertainty"] is True
    assert out["consensus_status"] == "high_uncertainty"
    assert out["final_signal_action"] == "none"
    assert out["signal_generation_aborted"] is False
    assert "Konflikt-Erkennung" in out["operator_explain"]["explanation_de"]


def test_weighted_consensus_buy_when_aligned() -> None:
    reg = AgentRegistry()
    reg.register(
        StubAgent(
            "macro_analyst",
            _msg(
                agent_id="macro_analyst",
                action="buy_bias",
                conf=0.8,
                rationale="Makro bestaetigt Long.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "quant_analyst",
            _msg(
                agent_id="quant_analyst",
                action="buy_bias",
                conf=0.85,
                rationale="Quant bestaetigt Long.",
            ),
        )
    )
    reg.register(
        StubAgent(
            "risk_governor",
            _msg(
                agent_id="risk_governor",
                action="allow",
                conf=0.75,
                rationale="Risk stimmt unter Vorbehalt zu.",
            ),
        )
    )
    orch = ConsensusOrchestrator(reg)
    out = asyncio.run(orch.evaluate({}))
    assert out["consensus_status"] == "ok"
    assert out["final_signal_action"] == "buy_bias"
    assert out["risk_hard_veto"] is False
    ex = out["operator_explain"]["explanation_de"]
    assert "Makro" in ex and "Quant" in ex and "Risk" in ex
