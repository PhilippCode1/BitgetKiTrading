from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.paths import load_json_schema, prompts_dir
from llm_orchestrator.providers.fake_provider import FakeProvider
from llm_orchestrator.providers.openai_provider import OpenAIProvider

logger = logging.getLogger("llm_orchestrator.agents.macro")


def _load_admin_operations_instruction() -> str:
    path = prompts_dir() / "tasks" / "admin_operations_assist.instruction_de.txt"
    return path.read_text(encoding="utf-8")


def _agent_schema() -> dict[str, Any]:
    return load_json_schema("agent_communication.schema.json")


def _onchain_whale_pressure(context: dict[str, Any]) -> float:
    oc = context.get("onchain_context") or {}
    if not isinstance(oc, dict):
        return 0.0
    p = float(oc.get("onchain_whale_pressure_0_1") or 0.0)
    recent = oc.get("recent_onchain_whale_events_json") or []
    if isinstance(recent, list) and recent:
        vol = sum(float(x.get("estimated_volume_usd") or 0) for x in recent if isinstance(x, dict))
        p = max(p, min(1.0, vol / 5_000_000.0))
    return max(0.0, min(1.0, p))


def _merge_social_sentiment_context(raw: dict[str, Any], context: dict[str, Any]) -> None:
    sc = context.get("social_context") or {}
    if not isinstance(sc, dict) or not sc:
        return
    try:
        roll = float(
            sc.get("rolling_sentiment_score")
            if sc.get("rolling_sentiment_score") is not None
            else sc.get("sentiment_score")
            or 0.0
        )
    except (TypeError, ValueError):
        return
    sp = raw.get("signal_proposal")
    if not isinstance(sp, dict):
        return
    pl = sp.get("payload")
    if not isinstance(pl, dict):
        pl = {}
    pl["social_rolling_sentiment_neg1_1"] = max(-1.0, min(1.0, roll))
    try:
        pl["social_panic_cosine"] = float(sc.get("panic_cosine") or 0.0)
        pl["social_euphoria_cosine"] = float(sc.get("euphoria_cosine") or 0.0)
    except (TypeError, ValueError):
        pass
    excerpt = str(sc.get("text_excerpt") or "").strip()
    if excerpt:
        pl["social_text_excerpt_de"] = excerpt[:400]
    prev_c = float(raw.get("confidence_0_1") or 0.5)
    adj = 1.0 + 0.12 * max(-1.0, min(1.0, roll))
    raw["confidence_0_1"] = max(0.05, min(0.98, prev_c * adj))
    sp["payload"] = pl
    raw["signal_proposal"] = sp


def _merge_onchain_whale_context(raw: dict[str, Any], context: dict[str, Any]) -> None:
    pressure = _onchain_whale_pressure(context)
    if pressure <= 0.0:
        return
    sp = raw.get("signal_proposal")
    if not isinstance(sp, dict):
        return
    pl = sp.get("payload")
    if not isinstance(pl, dict):
        pl = {}
    pl["onchain_whale_pressure_0_1"] = pressure
    prev_c = float(raw.get("confidence_0_1") or 0.5)
    raw["confidence_0_1"] = max(0.05, prev_c * (1.0 - 0.35 * pressure))
    sp["payload"] = pl
    raw["signal_proposal"] = sp


def _merge_news_shock_flag(raw: dict[str, Any], context: dict[str, Any]) -> None:
    news_obj = context.get("news_context") or context.get("news") or {}
    if not isinstance(news_obj, dict):
        return
    shock = bool(news_obj.get("news_shock"))
    if not shock:
        try:
            shock = float(news_obj.get("sentiment_score") or news_obj.get("sentiment") or 0.0) <= -0.85
        except (TypeError, ValueError):
            shock = False
    sp = raw.get("signal_proposal")
    if not isinstance(sp, dict):
        return
    pl = sp.get("payload")
    if not isinstance(pl, dict):
        pl = {}
    pl["news_shock"] = shock
    sp["payload"] = pl
    raw["signal_proposal"] = sp


class MacroAnalystAgent(BaseTradingAgent):
    """Globales News-/Sentiment-Reading per LLM; Instruktion aus Admin-Operations-Task (Referenz)."""

    def __init__(
        self,
        *,
        agent_id: str = "macro_analyst",
        settings: LLMOrchestratorSettings | None = None,
    ) -> None:
        super().__init__(agent_id=agent_id)
        self._settings = settings or LLMOrchestratorSettings()
        self._instruction = _load_admin_operations_instruction()
        self._openai = OpenAIProvider(settings=self._settings)
        self._fake = FakeProvider()

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        news = context.get("news_context") or context.get("news") or {}
        news_json = json.dumps(news, ensure_ascii=False, default=str)[: self._settings.llm_max_prompt_chars]
        social_json = json.dumps(context.get("social_context") or {}, ensure_ascii=False, default=str)[
            : self._settings.llm_max_prompt_chars // 6
        ]
        prompt = (
            "Du bist der Macro-Analyst der MARL-Flotte.\n"
            "Nutze die folgende Instruktionsschicht (Governance), den NEWS_KONTEXT und optional ONCHAIN_KONTEXT.\n"
            "Gewichtung: Bei Szenarien mit Liquidations- oder Wick-Risiko (harte Fills, Stops, kurzfristiger "
            "Gegenmove) sollen frische On-Chain-Wal-Fluesse hoch priorisiert werden: sie koennen Verkaufs-/"
            "Swap-Druck oder venue-lastige Kapitalverschiebung signalisieren, die chartrein schwer sichtbar ist. "
            "Erwaehne in der Begruendung explizit, wenn On-Chain-Befunde das Wick-/Liquidation-Szenario "
            "untermauern oder es relativieren (kein Trade-Rat, nur Einschaetzung).\n"
            "Keine Orderhoheit; nur Bewertung und strukturierte Agent-Nachricht.\n\n"
            f"=== Governance (Referenz: admin_operations_assist) ===\n{self._instruction}\n\n"
            f"NEWS_KONTEXT (JSON):\n{news_json}\n"
            f"ONCHAIN_KONTEXT (JSON, optional — Wal-Mempool / DEX-Impact):\n"
            f"{json.dumps(context.get('onchain_context') or {}, ensure_ascii=False, default=str)[: self._settings.llm_max_prompt_chars // 4]}\n"
            f"SOCIAL_KONTEXT (JSON, optional — Apex Embeddings / Panik-Kosinus):\n{social_json}\n"
        )
        schema = _agent_schema()
        try:
            if self._settings.llm_use_fake_provider:
                raw = await asyncio.to_thread(
                    self._fake.generate_structured,
                    schema,
                    prompt,
                    temperature=0.0,
                    timeout_ms=min(self._settings.llm_timeout_ms, 60_000),
                )
            elif self._openai.available:
                raw = await asyncio.to_thread(
                    self._openai.generate_structured,
                    schema,
                    prompt,
                    temperature=0.25,
                    timeout_ms=self._settings.llm_timeout_ms,
                    model=self._settings.openai_model_fast,
                    system_instructions_de=(
                        "Rolle: Macro-Analyst. Antworte nur mit JSON gemaess Schema "
                        "(agent-comm-v1). Keine Trades. "
                        "Wenn im ONCHAIN_KONTEXT Wal- oder DEX-Notional-Events genannt werden: "
                        "bei Themen Liquidation, Stop-Hunt, abrupte Wicks, Funding-Stress, "
                        "diese Befunde staerker als reine Preis-Chart-Extrema gewichten."
                    ),
                )
            else:
                raw = self._offline_payload(news_json)
            raw["agent_id"] = self.agent_id
            raw.setdefault("schema_version", "agent-comm-v1")
            _merge_news_shock_flag(raw, context)
            _merge_social_sentiment_context(raw, context)
            _merge_onchain_whale_context(raw, context)
            return self._finalize(raw)
        except Exception as exc:  # pragma: no cover — Netzwerkpfad
            logger.warning("MacroAnalystAgent: Analyse fehlgeschlagen: %s", exc)
            msg = self._offline_payload(news_json, note=str(exc))
            msg["agent_id"] = self.agent_id
            _merge_news_shock_flag(msg, context)
            _merge_social_sentiment_context(msg, context)
            _merge_onchain_whale_context(msg, context)
            return self._finalize(msg)

    def _offline_payload(self, news_excerpt: str, note: str | None = None) -> dict[str, Any]:
        rationale = (
            "Kein OpenAI-Aufruf (fehlender Key oder Fehler). "
            "News-Kontext wurde nicht LLM-bewertet; nur Platzhalter-Signal."
        )
        if note:
            rationale = f"{rationale} Technisch: {note[:500]}"
        shock = False
        try:
            news_obj = json.loads(news_excerpt) if news_excerpt.strip().startswith("{") else {}
        except json.JSONDecodeError:
            news_obj = {}
        if isinstance(news_obj, dict):
            shock = bool(news_obj.get("news_shock")) or float(news_obj.get("sentiment_score") or 0.0) <= -0.85
        return {
            "schema_version": "agent-comm-v1",
            "agent_id": self.agent_id,
            "status": "degraded",
            "confidence_0_1": 0.35,
            "rationale_de": rationale,
            "signal_proposal": {
                "action": "hold_research",
                "symbol": None,
                "timeframe": None,
                "payload": {
                    "news_digest_chars": len(news_excerpt),
                    "news_shock": shock,
                    "governance_ref": str(
                        Path("shared") / "prompts" / "tasks" / "admin_operations_assist.instruction_de.txt"
                    ),
                },
            },
            "evidence_refs": ["admin_operations_assist.instruction_de.txt"],
        }
