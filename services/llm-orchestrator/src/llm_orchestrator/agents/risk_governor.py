from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Literal

from llm_orchestrator.agents.ams_features import feature_vector_from_context
from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.toxicity_predictor import ToxicityClassifier
from llm_orchestrator.config import LLMOrchestratorSettings

logger = logging.getLogger("llm_orchestrator.agents.risk_governor")


def default_risk_governor_settings() -> Any:
    """Minimale Settings-Spiegel fuer ``assess_risk_governor`` ohne volle SignalEngineSettings."""
    return SimpleNamespace(
        signal_max_spread_bps=8.0,
        risk_governor_account_stress_live_only=True,
        risk_max_account_margin_usage=0.35,
        risk_max_account_drawdown_pct=0.10,
        risk_max_daily_drawdown_pct=0.04,
        risk_max_weekly_drawdown_pct=0.08,
        risk_max_daily_loss_usdt=1000.0,
        risk_governor_loss_streak_max=5,
        risk_governor_correlation_stress_abstain=0.88,
        risk_max_concurrent_positions=1,
        risk_portfolio_live_max_largest_position_risk_0_1=0.22,
        leverage_signal_min_depth_ratio=0.60,
        risk_force_reduce_only_on_alert=True,
        risk_governor_live_ramp_max_leverage=7,
        risk_portfolio_live_block_venue_degraded=True,
        risk_portfolio_live_max_family_exposure_0_1=0.58,
        risk_portfolio_live_max_direction_net_exposure_0_1=0.72,
        risk_portfolio_live_max_cluster_exposure_0_1=0.48,
        risk_portfolio_live_max_funding_drag_bps=95.0,
        risk_portfolio_live_max_basis_stress_0_1=0.62,
        risk_portfolio_live_max_session_concentration_0_1=0.88,
        risk_portfolio_live_max_open_orders_notional_ratio_0_1=0.42,
        risk_portfolio_live_max_pending_mirror_trades=4,
    )


class RiskGovernorAgent(BaseTradingAgent):
    """
    Portfolio-Risk-Governor: ``signal_engine.risk_governor`` plus AMS-Toxizitaets-RF (optional).

    - **live**: passives Monitoring — bei hoher Trap-Wahrscheinlichkeit harte Eskalation zu ``veto``.
    - **simulation**: keine harten Overrides; ``payload.ams_toxicity_eval`` fuer RL/Logging.
    """

    def __init__(
        self,
        *,
        agent_id: str = "risk_governor",
        risk_settings: Any | None = None,
        llm_settings: LLMOrchestratorSettings | None = None,
    ) -> None:
        super().__init__(agent_id=agent_id)
        self._risk_settings = risk_settings or default_risk_governor_settings()
        self._llm = llm_settings or LLMOrchestratorSettings()
        self._ams_mode: Literal["live", "simulation", "off"] = self._llm.risk_governor_ams_mode
        self._tox_thresh = float(self._llm.risk_governor_toxicity_veto_threshold_0_1)
        self._vpin_mode: Literal["live", "simulation", "off"] = self._llm.risk_governor_vpin_mode
        self._vpin_thresh = float(self._llm.risk_governor_vpin_veto_threshold_0_1)
        self._tox = ToxicityClassifier(self._llm.risk_governor_toxicity_model_path)

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        try:
            from signal_engine.risk_governor import assess_risk_governor
        except ImportError as exc:
            msg = {
                "schema_version": "agent-comm-v1",
                "agent_id": self.agent_id,
                "status": "blocked",
                "confidence_0_1": 0.0,
                "rationale_de": (
                    "signal_engine nicht importierbar — PYTHONPATH muss "
                    "`services/signal-engine/src` enthalten (siehe llm-orchestrator Dockerfile)."
                ),
                "signal_proposal": {
                    "action": "veto",
                    "symbol": None,
                    "timeframe": None,
                    "payload": {"import_error": str(exc)},
                },
                "evidence_refs": ["signal_engine/risk_governor.py"],
            }
            return self._finalize(msg)

        signal_row = context.get("signal_row")
        if not isinstance(signal_row, dict):
            raise ValueError("context['signal_row'] muss ein dict sein")
        direction = str(context.get("direction") or "long").strip().lower()

        gov = assess_risk_governor(
            settings=self._risk_settings,
            signal_row=signal_row,
            direction=direction,
        )
        veto = gov.get("trade_action_recommendation") == "do_not_trade" or bool(
            gov.get("universal_hard_block_reasons_json")
        )
        action = "veto" if veto else "allow"
        status = "blocked" if veto else "ok"
        conf = 0.25 if veto else 0.88
        rationale = (
            f"Risk-Governor {gov.get('version')}: trade_action_recommendation="
            f"{gov.get('trade_action_recommendation')!s}, quality_tier={gov.get('quality_tier')!s}, "
            f"hard_blocks={len(gov.get('hard_block_reasons_json') or [])}."
        )

        tox_p: float | None = None
        xvec = feature_vector_from_context(context)
        if xvec is not None and self._ams_mode != "off":
            tox_p = self._tox.predict_trap_proba(xvec)

        ams_eval: dict[str, Any] = {
            "ams_mode": self._ams_mode,
            "toxicity_trap_proba": tox_p,
            "toxicity_model_path": self._llm.risk_governor_toxicity_model_path,
        }
        truth = context.get("ams_ground_truth_trap")
        if isinstance(truth, bool):
            ams_eval["ground_truth_trap"] = truth
            if tox_p is not None:
                pred_trap = tox_p >= 0.5
                ams_eval["prediction_matches_truth"] = pred_trap == truth

        tox_override = False
        if (
            self._ams_mode == "live"
            and tox_p is not None
            and tox_p >= self._tox_thresh
            and action == "allow"
        ):
            tox_override = True
            action = "veto"
            status = "blocked"
            conf = max(conf, min(0.95, tox_p))
            rationale += (
                f" AMS/Order-Flow-Toxizitaet: RandomForest-Trap-Wahrscheinlichkeit {tox_p:.2f} "
                f">= Schwelle {self._tox_thresh:.2f} — Eskalation zu Veto (passives Monitoring)."
            )

        vpin_score: float | None = None
        raw_vpin = context.get("vpin_toxicity_0_1")
        if isinstance(raw_vpin, (int, float)):
            vpin_score = float(raw_vpin)
        else:
            tf = context.get("toxicity_features")
            if isinstance(tf, dict):
                rv = tf.get("vpin_toxicity_0_1")
                if isinstance(rv, (int, float)):
                    vpin_score = float(rv)

        ams_eval["vpin_eval"] = {
            "vpin_mode": self._vpin_mode,
            "vpin_toxicity_0_1": vpin_score,
            "vpin_veto_threshold_0_1": self._vpin_thresh,
        }
        if self._vpin_mode == "simulation" and vpin_score is not None and vpin_score >= self._vpin_thresh:
            ams_eval["vpin_eval"]["would_veto_in_live"] = True

        vpin_override = False
        if (
            self._vpin_mode == "live"
            and vpin_score is not None
            and vpin_score >= self._vpin_thresh
            and action == "allow"
        ):
            vpin_override = True
            action = "veto"
            status = "blocked"
            conf = max(conf, min(0.95, vpin_score))
            rationale += (
                f" VPIN/Orderflow-Toxizitaet: Score {vpin_score:.2f} "
                f">= Schwelle {self._vpin_thresh:.2f} — globaler Hard-Veto fuer neue Positionen."
            )

        msg = {
            "schema_version": "agent-comm-v1",
            "agent_id": self.agent_id,
            "status": status,
            "confidence_0_1": float(conf),
            "rationale_de": rationale,
            "signal_proposal": {
                "action": action,
                "symbol": context.get("symbol"),
                "timeframe": context.get("timeframe"),
                "payload": {
                    "governor": gov,
                    "ams_toxicity_eval": ams_eval,
                    "ams_toxicity_override_applied": tox_override,
                    "vpin_override_applied": vpin_override,
                },
            },
            "evidence_refs": [
                "signal_engine.risk_governor.assess_risk_governor",
                "adversarial-engine/ams_toxicity_classifier",
            ],
        }
        return self._finalize(msg)
