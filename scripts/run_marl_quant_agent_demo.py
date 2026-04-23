#!/usr/bin/env python3
"""
Demo: Feature-Engine -> QuantAnalystAgent -> schema-valide Agent-Nachricht.

Voraussetzungen:
- Laufende Feature-Engine (Standard http://127.0.0.1:8020) oder URL per FEATURE_ENGINE_URL.
- Optional: gebautes ``apex_core`` (Rust) auf PYTHONPATH fuer RSI-Smoke in der Nutzlast.

Aufruf vom Repo-Root::

    python scripts/run_marl_quant_agent_demo.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path


def _bootstrap_path() -> None:
    repo = Path(__file__).resolve().parents[1]
    for rel in (
        "services/llm-orchestrator/src",
        "services/signal-engine/src",
        "shared/python/src",
    ):
        p = repo / rel
        if p.is_dir():
            sys.path.insert(0, str(p))


async def _main() -> None:
    _bootstrap_path()
    os.environ.setdefault("REDIS_URL", os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"))

    from llm_orchestrator.agents.quant import QuantAnalystAgent
    from llm_orchestrator.agents.contract import validate_agent_message

    base = os.environ.get("FEATURE_ENGINE_URL", "http://127.0.0.1:8020").rstrip("/")
    symbol = os.environ.get("DEMO_SYMBOL", "BTCUSDT")
    timeframe = os.environ.get("DEMO_TIMEFRAME", "1m")

    agent = QuantAnalystAgent(feature_engine_base_url=base)
    msg = await agent.analyze({"symbol": symbol, "timeframe": timeframe})
    validate_agent_message(msg)
    print(json.dumps(msg, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(_main())
