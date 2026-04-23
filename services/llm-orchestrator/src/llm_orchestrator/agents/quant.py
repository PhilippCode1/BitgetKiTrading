from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from llm_orchestrator.agents.base import BaseTradingAgent
from llm_orchestrator.agents.tsfm_semantics import synthesize_tsfm_signal
from llm_orchestrator.agents.tsfm_types import TsfmSignalCandidatePayloadV1

logger = logging.getLogger("llm_orchestrator.agents.quant")


def _extract_tsfm_candidate(context: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("tsfm_signal_candidate", "TSFM_SIGNAL_CANDIDATE"):
        raw = context.get(key)
        if isinstance(raw, dict) and str(raw.get("schema") or "") == "tsfm_signal_candidate/v1":
            return raw
    for nest_key in ("market_event", "event", "envelope"):
        inner = context.get(nest_key)
        if not isinstance(inner, dict):
            continue
        cand = inner.get("tsfm_signal_candidate") or inner.get("payload")
        if isinstance(cand, dict) and str(cand.get("schema") or "") == "tsfm_signal_candidate/v1":
            return cand
    return None


class QuantAnalystAgent(BaseTradingAgent):
    """Primär TimesFM-Patch (Eventbus-Kontext); Fallback Feature-Engine-HTTP."""

    def __init__(
        self,
        *,
        agent_id: str = "quant_analyst",
        feature_engine_base_url: str = "http://127.0.0.1:8020",
        http_timeout_sec: float = 10.0,
    ) -> None:
        super().__init__(agent_id=agent_id)
        self._base = str(feature_engine_base_url).rstrip("/")
        self._http_timeout = float(http_timeout_sec)

    async def _fetch_correlation_matrix(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        try:
            r = await client.get(
                f"{self._base}/correlation/matrix",
                timeout=min(self._http_timeout, 15.0),
            )
            if r.status_code != 200:
                return None
            body = r.json()
            if isinstance(body, dict) and body.get("status") == "ok":
                c = body.get("correlation")
                return c if isinstance(c, dict) else None
        except Exception as exc:
            logger.debug("correlation matrix fetch skipped: %s", exc)
        return None

    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        t0 = time.perf_counter_ns()
        symbol = str(context.get("symbol") or "BTCUSDT").strip().upper()
        timeframe = str(context.get("timeframe") or "1m").strip()
        canonical_instrument_id = context.get("canonical_instrument_id")
        market_family = context.get("market_family")

        corr_bundle: dict[str, Any] | None = None
        try:
            async with httpx.AsyncClient(timeout=min(self._http_timeout, 12.0)) as ccorr:
                corr_bundle = await self._fetch_correlation_matrix(ccorr)
        except Exception as exc:
            logger.debug("correlation client: %s", exc)
        if context.get("intermarket_correlation") and isinstance(context["intermarket_correlation"], dict):
            corr_bundle = context["intermarket_correlation"]

        raw_tsfm = _extract_tsfm_candidate(context)
        tsfm_model = TsfmSignalCandidatePayloadV1.from_envelope_payload(raw_tsfm)
        if tsfm_model is not None:
            synthesis = synthesize_tsfm_signal(tsfm_model)
            bias = synthesis.directional_bias
            if bias == "long":
                action, conf = "buy_bias", float(synthesis.synthesis_confidence_0_1)
            elif bias == "short":
                action, conf = "sell_bias", float(synthesis.synthesis_confidence_0_1)
            else:
                action, conf = "hold_research", max(0.12, float(synthesis.synthesis_confidence_0_1) * 0.85)
            elapsed_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
            apex_payload = self._apex_smoke()
            corr_note = ""
            if corr_bundle and isinstance((corr_bundle.get("regime_divergence") or {}), dict):
                rd = corr_bundle["regime_divergence"]
                if rd.get("triggered"):
                    corr_note = (
                        " Intermarket-Divergenz: UUP (USD-Proxy) vs BTC deutlich entkoppelt — "
                        "REGIME_DIVERGENCE_DETECTED im Eventbus pruefen."
                    )
            rationale = synthesis.narrative_de + (
                f" Latenz Quant-Pfad (ohne Feature-HTTP): {elapsed_ms:.2f} ms.{corr_note}"
            )
            msg = {
                "schema_version": "agent-comm-v1",
                "agent_id": self.agent_id,
                "status": "ok",
                "confidence_0_1": float(min(0.99, max(0.05, conf))),
                "rationale_de": rationale,
                "signal_proposal": {
                    "action": action,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "payload": {
                        "tsfm_primary_source": True,
                        "tsfm_model_confidence_0_1": float(tsfm_model.confidence_0_1),
                        "tsfm_directional_bias": bias,
                        "tsfm_semantic_synthesis": synthesis.model_dump(),
                        "tsfm_signal_candidate": tsfm_model.model_dump(by_alias=True),
                        "quant_foundation_path_ms": round(elapsed_ms, 3),
                        "apex_core": apex_payload,
                    },
                },
                "evidence_refs": [
                    "eventbus:tsfm_signal_candidate/v1",
                    f"forecast_sha256:{tsfm_model.forecast_sha256[:24]}...",
                ],
            }
            return self._finalize(msg)

        params: dict[str, Any] = {"symbol": symbol, "timeframe": timeframe}
        if canonical_instrument_id:
            params["canonical_instrument_id"] = str(canonical_instrument_id)
        if market_family:
            params["market_family"] = str(market_family)

        feature: dict[str, Any] | None = None
        async with httpx.AsyncClient(timeout=self._http_timeout) as client:
            url = f"{self._base}/features/latest"
            resp = await client.get(url, params=params)
            if resp.status_code == 404:
                msg = self._no_feature_message(symbol, timeframe, resp.text[:300])
                msg["agent_id"] = self.agent_id
                return self._finalize(msg)
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, dict) and body.get("status") == "ok":
                feature = body.get("feature")
                if not isinstance(feature, dict):
                    feature = None

        if not feature:
            msg = self._no_feature_message(symbol, timeframe, "leerer Response-Body")
            msg["agent_id"] = self.agent_id
            return self._finalize(msg)

        rsi = feature.get("rsi_14")
        momentum = feature.get("momentum_score")
        apex_payload = self._apex_smoke()

        action = "none"
        conf = 0.55
        if isinstance(rsi, (int, float)):
            if float(rsi) < 35:
                action, conf = "buy_bias", min(0.92, 0.55 + (35 - float(rsi)) / 100)
            elif float(rsi) > 65:
                action, conf = "sell_bias", min(0.92, 0.55 + (float(rsi) - 65) / 100)
        if isinstance(momentum, (int, float)) and action == "none":
            if float(momentum) > 0.25:
                action, conf = "buy_bias", 0.62
            elif float(momentum) < -0.25:
                action, conf = "sell_bias", 0.62

        corr_note = ""
        if corr_bundle and isinstance((corr_bundle.get("regime_divergence") or {}), dict):
            if (corr_bundle["regime_divergence"] or {}).get("triggered"):
                corr_note = " Intermarket: Divergenz UUP vs BTC (Decoupling-Hinweis)."
        rationale = (
            f"Feature-Engine Zeile fuer {symbol} {timeframe}: rsi_14={rsi!s}, "
            f"momentum_score={momentum!s}. Rust-Bruecke: {apex_payload.get('apex_core_status')!s}.{corr_note}"
        )
        msg = {
            "schema_version": "agent-comm-v1",
            "agent_id": self.agent_id,
            "status": "ok",
            "confidence_0_1": float(conf),
            "rationale_de": rationale,
            "signal_proposal": {
                "action": action,
                "symbol": symbol,
                "timeframe": timeframe,
                "payload": {
                    "tsfm_primary_source": False,
                    "feature_engine_base": self._base,
                    "rsi_14": rsi,
                    "momentum_score": momentum,
                    "trend_dir": feature.get("trend_dir"),
                    "apex_core": apex_payload,
                    "intermarket_correlation": corr_bundle,
                },
            },
            "evidence_refs": [f"GET {self._base}/features/latest"],
        }
        return self._finalize(msg)

    def _apex_smoke(self) -> dict[str, Any]:
        try:
            import numpy as np

            import apex_core  # type: ignore[import-not-found]

            closes = np.linspace(100.0, 102.0, 80, dtype=np.float64)
            rsi_rust = float(apex_core.compute_rsi_sma(closes, 14))
            return {"apex_core_status": "ok", "rsi_smoke_series": rsi_rust}
        except Exception as exc:
            logger.debug("apex_core smoke skipped: %s", exc)
            return {"apex_core_status": "unavailable", "error": str(exc)[:200]}

    def _no_feature_message(self, symbol: str, timeframe: str, detail: str) -> dict[str, Any]:
        return {
            "schema_version": "agent-comm-v1",
            "agent_id": self.agent_id,
            "status": "degraded",
            "confidence_0_1": 0.2,
            "rationale_de": (
                f"Keine Feature-Zeile von der Engine fuer {symbol} {timeframe}. "
                f"Detail: {detail[:400]}"
            ),
            "signal_proposal": {
                "action": "hold_research",
                "symbol": symbol,
                "timeframe": timeframe,
                "payload": {"reason": "feature_row_missing", "tsfm_primary_source": False},
            },
            "evidence_refs": [],
        }
