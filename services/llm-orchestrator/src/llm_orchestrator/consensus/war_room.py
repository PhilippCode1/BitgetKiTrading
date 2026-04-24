"""
War-Room / Konsensus: parallele Agenten, gewichtete Fusion, hartes Risk-Veto.

Inspiriert von signal_engine.meta_decision_kernel (Abstinenz-Codes, kein stilles Override).
"""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from typing import Any

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.contract import validate_agent_message
from llm_orchestrator.agents.registry import AgentRegistry
from llm_orchestrator.config import LLMOrchestratorSettings
from llm_orchestrator.paths import load_json_schema
from llm_orchestrator.validation.schema_validate import validate_against_schema
from llm_orchestrator.consensus.tsfm_learning_feedback import post_tsfm_war_room_audit
from llm_orchestrator.knowledge.onchain_macro import (
    build_readonly_onchain_text,
    fetch_onchain_macro_context,
    merge_fetched_onchain_into_context,
)
from llm_orchestrator.consensus.specialist_precision import (
    apply_precision_to_weights,
    extract_market_regime,
    fetch_specialist_precision_block,
    log_weighted_stakes_pre_consensus,
    precision_0_1_by_agent,
    precision_stake_multiplier,
)

logger = logging.getLogger("llm_orchestrator.consensus.war_room")

WAR_ROOM_VERSION = "war-room-v1"

MACRO_ID = "macro_analyst"
QUANT_ID = "quant_analyst"
RISK_ID = "risk_governor"


def _action_direction_unit(action: str) -> float:
    a = (action or "").strip().lower()
    if a == "buy_bias":
        return 1.0
    if a == "sell_bias":
        return -1.0
    return 0.0


def _synthetic_timeout_message(agent_id: str, detail: str) -> dict[str, Any]:
    return {
        "schema_version": "agent-comm-v1",
        "agent_id": agent_id,
        "status": "degraded",
        "confidence_0_1": 0.0,
        "rationale_de": f"Agent-Timeout oder technischer Fehler: {detail[:800]}",
        "signal_proposal": {
            "action": "none",
            "symbol": None,
            "timeframe": None,
            "payload": {"timeout_or_error": True},
        },
        "evidence_refs": [],
    }


def _risk_hard_veto(risk_msg: dict[str, Any]) -> bool:
    if risk_msg.get("agent_id") != RISK_ID:
        return False
    prop = risk_msg.get("signal_proposal") or {}
    if prop.get("action") == "veto":
        return True
    gov = prop.get("payload") or {}
    if isinstance(gov, dict):
        inner = gov.get("governor") or {}
        if isinstance(inner, dict):
            if inner.get("trade_action_recommendation") == "do_not_trade":
                return True
            if inner.get("universal_hard_block_reasons_json"):
                return True
    return False


def _quant_tsfm_payload(quant_m: dict[str, Any]) -> dict[str, Any]:
    pl = (quant_m.get("signal_proposal") or {}).get("payload")
    return pl if isinstance(pl, dict) else {}


def _macro_news_shock(macro_m: dict[str, Any], market_event: dict[str, Any]) -> bool:
    news = market_event.get("news_context") or market_event.get("news") or {}
    if isinstance(news, dict):
        if bool(news.get("news_shock")):
            return True
        try:
            s = float(news.get("sentiment_score") or news.get("sentiment") or 0.0)
            if s <= -0.85:
                return True
        except (TypeError, ValueError):
            pass
    mpl = (macro_m.get("signal_proposal") or {}).get("payload")
    if isinstance(mpl, dict) and bool(mpl.get("news_shock")):
        return True
    return False


def _quant_proposes_directional(quant_m: dict[str, Any]) -> bool:
    a = str((quant_m.get("signal_proposal") or {}).get("action") or "").strip().lower()
    return a in ("buy_bias", "sell_bias")


def _tsfm_long_exposure(quant_m: dict[str, Any]) -> bool:
    pl = _quant_tsfm_payload(quant_m)
    if not bool(pl.get("tsfm_primary_source")):
        return False
    if str(pl.get("tsfm_directional_bias") or "").lower() == "long":
        return True
    act = str((quant_m.get("signal_proposal") or {}).get("action") or "").lower()
    return act == "buy_bias"


def _consensus_weight_vector(
    base_weights: dict[str, float], quant_m: dict[str, Any]
) -> tuple[dict[str, float], float, float]:
    """Gibt normierte Gewichte, Basis-Quant-Gewicht und effektives Quant-Gewicht zurueck."""
    w = {k: float(v) for k, v in base_weights.items()}
    w0q = float(w.get(QUANT_ID, 0.47))
    pl = _quant_tsfm_payload(quant_m)
    tsfm_c = float(pl.get("tsfm_model_confidence_0_1") or 0.0)
    if bool(pl.get("tsfm_primary_source")) and tsfm_c > 0.9:
        w[QUANT_ID] = w0q * 1.45
    s = sum(max(v, 1e-9) for v in w.values())
    wn = {k: v / s for k, v in w.items()}
    return wn, w0q, float(wn.get(QUANT_ID, w0q))


def _macro_quant_divergence(macro: dict[str, Any], quant: dict[str, Any]) -> bool:
    ma = str((macro.get("signal_proposal") or {}).get("action") or "").strip().lower()
    qa = str((quant.get("signal_proposal") or {}).get("action") or "").strip().lower()
    bull, bear = {"buy_bias"}, {"sell_bias"}
    if ma in bull and qa in bear:
        return True
    if ma in bear and qa in bull:
        return True
    mc = float(macro.get("confidence_0_1") or 0.0)
    qc = float(quant.get("confidence_0_1") or 0.0)
    if ma == "hold_research" and qa in bull and qc >= 0.72:
        return True
    if qa == "hold_research" and ma in bull and mc >= 0.72:
        return True
    if ma == "hold_research" and qa in bear and qc >= 0.72:
        return True
    if qa == "hold_research" and ma in bear and mc >= 0.72:
        return True
    return False


def _build_operator_explain(
    *,
    consensus_status: str,
    final_action: str,
    risk_veto: bool,
    high_uncertainty: bool,
    lines: list[str],
    foundation_lines: list[str] | None = None,
) -> dict[str, Any]:
    all_lines = list(lines)
    if foundation_lines:
        all_lines.extend(foundation_lines)
    explain = " ".join(all_lines).strip()
    if len(explain) > 24_000:
        explain = explain[:24_000] + " …"
    payload = {
        "schema_version": "1.0",
        "execution_authority": "none",
        "explanation_de": explain or "Keine Begründung erzeugt.",
        "referenced_artifacts_de": [
            "shared/contracts/schemas/agent_communication.schema.json",
            "shared/contracts/schemas/operator_explain.schema.json",
            MACRO_ID,
            QUANT_ID,
            RISK_ID,
            f"consensus:{consensus_status}",
        ],
        "non_authoritative_note_de": (
            "War-Room-Konsensus des llm-orchestrator: keine Orderhoheit, keine Parameteränderung. "
            "Risk-Governor-Veto bricht die Signal-Freigabe unabhängig von Makro/Quant ab. "
            f"Status={consensus_status}, final_action={final_action}, "
            f"risk_veto={risk_veto}, high_uncertainty={high_uncertainty}."
        ),
    }
    validate_against_schema(load_json_schema("operator_explain.schema.json"), payload)
    return payload


class ConsensusOrchestrator:
    """Router-basierte War-Room-Logik: parallel, gewichtet, Risk-Veto, Audit-Trail."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        settings: LLMOrchestratorSettings | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings or LLMOrchestratorSettings()
        self._weights = weights or {
            MACRO_ID: 0.28,
            QUANT_ID: 0.47,
            RISK_ID: 0.25,
        }

    def _timeout_sec(self, override: float | None) -> float:
        if override is not None:
            return max(1.0, min(120.0, float(override)))
        return max(1.0, min(120.0, float(self._settings.war_room_agent_timeout_sec)))

    async def _run_one(
        self, agent: BaseTradingAgent, context: dict[str, Any], timeout_sec: float
    ) -> dict[str, Any]:
        try:
            raw = await asyncio.wait_for(agent.analyze(context), timeout=timeout_sec)
            validate_agent_message(raw)
            return raw
        except asyncio.TimeoutError:
            logger.warning("War-Room: Timeout agent_id=%s after %ss", agent.agent_id, timeout_sec)
            msg = _synthetic_timeout_message(agent.agent_id, "Timeout")
            validate_agent_message(msg)
            return msg
        except Exception as exc:  # pragma: no cover — defensive
            logger.exception("War-Room: Agent-Fehler agent_id=%s", agent.agent_id)
            msg = _synthetic_timeout_message(agent.agent_id, str(exc))
            validate_agent_message(msg)
            return msg

    async def evaluate(
        self,
        market_event: dict[str, Any],
        *,
        agent_timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        """
        Führt Macro, Quant, Risk parallel aus; Risk-Veto stoppt Freigabe;
        Divergenz Makro/Quant -> high_uncertainty.
        """
        me: dict[str, Any] = copy.deepcopy(market_event) if isinstance(
            market_event, dict
        ) else {}
        if isinstance(market_event, dict):
            try:
                fetched = await asyncio.to_thread(
                    fetch_onchain_macro_context,
                    self._settings.redis_url,
                )
                me = merge_fetched_onchain_into_context(me, fetched)
            except Exception as exc:  # pragma: no cover — defensiv
                logger.warning("war_room: onchain_macro: %s", exc)

        wall0 = time.perf_counter()
        timeout = self._timeout_sec(agent_timeout_sec)
        agents = [
            self._registry.get(MACRO_ID),
            self._registry.get(QUANT_ID),
            self._registry.get(RISK_ID),
        ]
        results = await asyncio.gather(
            *[self._run_one(a, me, timeout) for a in agents],
            return_exceptions=False,
        )
        by_id = {m["agent_id"]: m for m in results}
        macro_m = by_id[MACRO_ID]
        quant_m = by_id[QUANT_ID]
        risk_m = by_id[RISK_ID]

        regime_label = extract_market_regime(me)
        try:
            precision_block = await asyncio.to_thread(
                fetch_specialist_precision_block,
                self._settings,
                market_regime=regime_label,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("war_room: specialist precision block: %s", exc)
            precision_block = {"status": "error", "specialists": {}}
        prec_by_agent = precision_0_1_by_agent(
            precision_block if isinstance(precision_block, dict) else None
        )
        base_w = dict(self._weights)
        w_adj = apply_precision_to_weights(base_w, prec_by_agent)
        log_weighted_stakes_pre_consensus(
            market_regime=regime_label,
            base_weights=base_w,
            precision_0_1=prec_by_agent,
            adjusted_weights_unnormalized=w_adj,
        )
        weights_eff, quant_w_base, quant_w_eff = _consensus_weight_vector(w_adj, quant_m)
        news_shock = _macro_news_shock(macro_m, me)
        tsfm_long = _tsfm_long_exposure(quant_m)
        shock_penalty = bool(news_shock and tsfm_long)
        quant_for_score = copy.deepcopy(quant_m)
        if shock_penalty:
            qc0 = float(quant_for_score.get("confidence_0_1") or 0.0)
            quant_for_score["confidence_0_1"] = max(0.03, qc0 * 0.15)
            qpl = (quant_for_score.get("signal_proposal") or {}).get("payload")
            if isinstance(qpl, dict):
                qpl["news_shock_downgrade"] = True
                qpl["news_shock_downgrade_factor"] = 0.15

        veto = _risk_hard_veto(risk_m)
        divergent = _macro_quant_divergence(macro_m, quant_for_score)

        lines = [
            f"Makro ({MACRO_ID}): {macro_m.get('signal_proposal', {}).get('action')} "
            f"(Konfidenz {macro_m.get('confidence_0_1')}). "
            f"{macro_m.get('rationale_de', '')[:1200]}",
            f"Quant ({QUANT_ID}): {quant_m.get('signal_proposal', {}).get('action')} "
            f"(Konfidenz {quant_m.get('confidence_0_1')}). "
            f"{quant_m.get('rationale_de', '')[:1200]}",
            f"Risk ({RISK_ID}): {risk_m.get('signal_proposal', {}).get('action')} "
            f"(Konfidenz {risk_m.get('confidence_0_1')}). "
            f"{risk_m.get('rationale_de', '')[:1200]}",
        ]

        plq = _quant_tsfm_payload(quant_m)
        foundation_lines: list[str] = []
        if bool(plq.get("tsfm_primary_source")):
            foundation_lines.append(
                f"Foundation Model (TimesFM): Richtungs-Bias `{plq.get('tsfm_directional_bias')}`, "
                f"Modell-Konfidenz {float(plq.get('tsfm_model_confidence_0_1') or 0):.2f}, "
                f"Quant-Gewicht effektiv {quant_w_eff:.3f} (Basis {quant_w_base:.3f})."
            )
        if shock_penalty:
            foundation_lines.append(
                "Cross-Check: TimesFM-Long-Signal bei News-Schock (Macro/news-engine) — "
                "Quant-Konfidenz fuer den Konsens massiv abgewertet."
            )

        soc = me.get("social_context") or {}
        if isinstance(soc, dict) and soc:
            try:
                s_roll = float(soc.get("rolling_sentiment_score") or soc.get("sentiment_score") or 0.0)
                s_inst = float(soc.get("sentiment_score") or 0.0)
                p_cos = float(soc.get("panic_cosine") or 0.0)
                e_cos = float(soc.get("euphoria_cosine") or 0.0)
            except (TypeError, ValueError):
                s_roll = s_inst = p_cos = e_cos = 0.0
            foundation_lines.append(
                f"Social-Sentiment (Apex/news-engine): rollierend {s_roll:+.2f}, "
                f"Momentan {s_inst:+.2f}, Panik-Kosinus {p_cos:.3f}, Euphorie-Kosinus {e_cos:.3f} "
                f"(Einbettung vs. Referenz-Zentroiden; kein Order-Signal)."
            )
        otxt = build_readonly_onchain_text(me)
        octxm = (me.get("onchain_context") or {}) if isinstance(
            me.get("onchain_context"), dict
        ) else {}
        o_press = float(octxm.get("onchain_whale_pressure_0_1") or 0.0)
        if otxt.strip():
            foundation_lines.append(
                f"On-Chain / Whale (Sniffer-Stream, Kuerzel): Druck-Score {o_press:.2f}. "
                f"Details: {otxt[:1800]}"
            )
        elif o_press > 0:
            foundation_lines.append(
                f"On-Chain: Wal-Druck-Indikator {o_press:.2f} (ohne lesbare Textzeilen)."
            )

        weighted = 0.0
        w_sum = 0.0
        for aid, msg in ((MACRO_ID, macro_m), (QUANT_ID, quant_for_score)):
            w = float(weights_eff.get(aid, 0.0))
            c = float(msg.get("confidence_0_1") or 0.0)
            u = _action_direction_unit(str((msg.get("signal_proposal") or {}).get("action") or ""))
            weighted += w * c * u
            w_sum += w * max(c, 1e-6)

        if w_sum > 0:
            weighted /= w_sum

        final_action = "none"
        consensus_status = "ok"

        if veto:
            consensus_status = "veto_aborted"
            final_action = "none"
            weighted = 0.0
            lines.append(
                "Risk-Governor: **Hard-Veto** — Signalgenerierung abgebrochen (Vorrang vor Makro/Quant)."
            )
            if _quant_proposes_directional(quant_m):
                lines.append(
                    "Readiness (konservativ): Quant liefert Richtung (BUY/SELL-Bias), Risk lehnt ab (Veto) — "
                    "finale Entscheidung bleibt do_not_trade (kein Signal), unabhaengig von Makro/Quant-Konfidenz."
                )
        elif divergent:
            consensus_status = "high_uncertainty"
            final_action = "none"
            lines.append(
                "Konflikt-Erkennung: Makro und Quant widersprechen sich stark "
                "(High Uncertainty / mdk_abstain_specialist_divergence-Analogon)."
            )
        else:
            if weighted > 0.18:
                final_action = "buy_bias"
            elif weighted < -0.18:
                final_action = "sell_bias"
            else:
                final_action = "none"
            lines.append(
                f"Gewichteter Konsens-Score (Bayes-artige Normierung): {weighted:.4f} → {final_action}."
            )

        operator_explain = _build_operator_explain(
            consensus_status=consensus_status,
            final_action=final_action,
            risk_veto=veto,
            high_uncertainty=divergent and not veto,
            lines=lines,
            foundation_lines=foundation_lines or None,
        )

        wall_ms = (time.perf_counter() - wall0) * 1000.0
        tsfm_pl = _quant_tsfm_payload(quant_m)
        synth = tsfm_pl.get("tsfm_semantic_synthesis") if isinstance(tsfm_pl, dict) else None
        fcand = tsfm_pl.get("tsfm_signal_candidate") if isinstance(tsfm_pl, dict) else None
        fsha = None
        if isinstance(fcand, dict):
            fsha = fcand.get("forecast_sha256")
        anchor = me.get("last_price") or me.get("mark_price")
        try:
            anchor_f = float(anchor) if anchor is not None else None
        except (TypeError, ValueError):
            anchor_f = None

        social_ctx = me.get("social_context")
        social_roll = 0.0
        if isinstance(social_ctx, dict):
            try:
                social_roll = float(
                    social_ctx.get("rolling_sentiment_score")
                    or social_ctx.get("sentiment_score")
                    or 0.0
                )
            except (TypeError, ValueError):
                social_roll = 0.0

        foundation_model_audit: dict[str, Any] = {
            "market_regime_for_precision": regime_label,
            "specialist_ai_precision_0_1": {
                a: float(prec_by_agent.get(a) or 0.0) for a in (MACRO_ID, QUANT_ID, RISK_ID)
            },
            "specialist_stake_multipliers": {
                a: float(precision_stake_multiplier(float(prec_by_agent.get(a) or 0.0)))
                for a in (MACRO_ID, QUANT_ID, RISK_ID)
            },
            "specialist_precision_status": str(precision_block.get("status"))
            if isinstance(precision_block, dict) and precision_block.get("status") is not None
            else None,
            "tsfm_primary": bool(tsfm_pl.get("tsfm_primary_source")),
            "tsfm_model_confidence_0_1": tsfm_pl.get("tsfm_model_confidence_0_1"),
            "tsfm_directional_bias": tsfm_pl.get("tsfm_directional_bias"),
            "forecast_sha256_prefix": (str(fsha)[:20] + "...") if fsha else None,
            "quant_weight_base": quant_w_base,
            "quant_weight_effective": quant_w_eff,
            "weights_effective": weights_eff,
            "macro_news_shock": news_shock,
            "social_rolling_sentiment_neg1_1": social_roll,
            "onchain_whale_pressure_0_1": float(
                (me.get("onchain_context") or {}).get("onchain_whale_pressure_0_1") or 0.0
            ),
            "shock_penalty_applied": shock_penalty,
            "quant_confidence_original_0_1": float(quant_m.get("confidence_0_1") or 0.0),
            "quant_confidence_for_consensus_0_1": float(quant_for_score.get("confidence_0_1") or 0.0),
            "quant_foundation_path_ms": tsfm_pl.get("quant_foundation_path_ms"),
            "war_room_eval_wall_ms": round(wall_ms, 3),
            "semantic_synthesis": synth if isinstance(synth, dict) else None,
        }

        if self._settings.tsfm_learning_feedback_enabled and bool(tsfm_pl.get("tsfm_primary_source")):
            rec_ms = int(time.time() * 1000)
            tsfm_c = tsfm_pl.get("tsfm_model_confidence_0_1")
            horizon = None
            if isinstance(fcand, dict):
                try:
                    horizon = int(fcand.get("forecast_horizon") or 0) or None
                except (TypeError, ValueError):
                    horizon = None
            audit_body = {
                "recorded_ts_ms": rec_ms,
                "symbol": str((quant_m.get("signal_proposal") or {}).get("symbol") or "BTCUSDT"),
                "forecast_sha256": str(fsha) if fsha else None,
                "tsfm_direction": str(tsfm_pl.get("tsfm_directional_bias") or ""),
                "tsfm_confidence_0_1": float(tsfm_c) if tsfm_c is not None else None,
                "tsfm_horizon_ticks": horizon,
                "quant_action": str((quant_m.get("signal_proposal") or {}).get("action") or ""),
                "quant_confidence_0_1": float(quant_m.get("confidence_0_1") or 0.0),
                "quant_confidence_effective_0_1": float(quant_for_score.get("confidence_0_1") or 0.0),
                "macro_action": str((macro_m.get("signal_proposal") or {}).get("action") or ""),
                "macro_news_shock": news_shock,
                "onchain_whale_pressure_0_1": float(
                    (me.get("onchain_context") or {}).get("onchain_whale_pressure_0_1") or 0.0
                ),
                "consensus_action": final_action,
                "consensus_status": consensus_status,
                "quant_weight_base": quant_w_base,
                "quant_weight_effective": quant_w_eff,
                "shock_penalty_applied": shock_penalty,
                "anchor_price": anchor_f,
                "quant_foundation_path_ms": float(tsfm_pl["quant_foundation_path_ms"])
                if tsfm_pl.get("quant_foundation_path_ms") is not None
                else None,
                "war_room_eval_wall_ms": round(wall_ms, 3),
                "payload": {
                    "foundation_model_audit": foundation_model_audit,
                    "operator_explain_excerpt_de": (operator_explain.get("explanation_de") or "")[:4000],
                },
            }
            asyncio.create_task(post_tsfm_war_room_audit(self._settings, audit_body))

        return {
            "version": WAR_ROOM_VERSION,
            "consensus_status": consensus_status,
            "final_signal_action": final_action,
            "weighted_directional_score": float(weighted),
            "risk_hard_veto": veto,
            "macro_quant_high_uncertainty": bool(divergent),
            "signal_generation_aborted": bool(veto),
            "agent_messages": results,
            "operator_explain": operator_explain,
            "foundation_model_audit": foundation_model_audit,
        }
