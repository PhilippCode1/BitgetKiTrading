from __future__ import annotations

from typing import Any

from signal_engine.config import SignalEngineSettings
from signal_engine.explain.schemas import ExplainInput
from signal_engine.news_compat import news_sentiment_as_float
from signal_engine.scoring.risk_score import _first_geometry


def build_risk_warnings(inp: ExplainInput, settings: SignalEngineSettings) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    s = inp.signal_row
    direction = str(s.get("direction", "neutral"))
    analysis_ts = int(s.get("analysis_ts_ms", 0))
    pf = inp.primary_feature

    if pf is not None:
        ct = int(pf.get("computed_ts_ms") or 0)
        if ct > 0 and analysis_ts - ct > settings.signal_max_data_age_ms:
            out.append(
                {
                    "code": "STALE_DATA",
                    "severity": "high",
                    "message": "Feature-Daten aelter als SIGNAL_MAX_DATA_AGE_MS.",
                    "evidence": {
                        "analysis_ts_ms": analysis_ts,
                        "feature_computed_ts_ms": ct,
                        "max_age_ms": settings.signal_max_data_age_ms,
                    },
                }
            )

    close = inp.last_close
    atr_14 = None
    if pf is not None and pf.get("atr_14") is not None:
        atr_14 = float(pf["atr_14"])
    stop_geo = _first_geometry(inp.drawings, "stop_zone")

    if close is not None and atr_14 is not None and atr_14 > 0 and stop_geo is not None:
        try:
            slo = float(stop_geo["price_low"])
            shi = float(stop_geo["price_high"])
            smid = (slo + shi) / 2.0
            dist = abs(close - smid)
            min_dist = settings.stop_min_atr_mult * atr_14
            if dist < min_dist:
                out.append(
                    {
                        "code": "STOP_TOO_TIGHT_FOR_ATR",
                        "severity": "medium",
                        "message": "Stop-Distanz kleiner als STOP_MIN_ATR_MULT * ATR(14).",
                        "evidence": {
                            "distance": dist,
                            "min_required": min_dist,
                            "atr_14": atr_14,
                            "mult": settings.stop_min_atr_mult,
                        },
                    }
                )
        except (KeyError, TypeError, ValueError):
            pass

    # 1H / 4H Trend vs. Richtung
    if direction in ("long", "short"):
        want = 1 if direction == "long" else -1
        conflicting: list[dict[str, Any]] = []
        for tf in ("1H", "4H"):
            row = inp.features_by_tf.get(tf)
            if row is None:
                continue
            try:
                td = int(row.get("trend_dir", 0))
            except (TypeError, ValueError):
                td = 0
            if td != 0 and td != want:
                conflicting.append({"timeframe": tf, "feature_trend_dir": td})
        if conflicting:
            out.append(
                {
                    "code": "CONFLICT_HIGH_TF",
                    "severity": "high",
                    "message": "Hoehere Zeitrahmen (1H/4H) widersprechen der Signalrichtung.",
                    "evidence": {
                        "signal_direction": direction,
                        "conflicts": conflicting,
                    },
                }
            )

    for ev in inp.structure_events[:15]:
        if str(ev.get("type")) == "FALSE_BREAKOUT":
            out.append(
                {
                    "code": "BREAKOUT_FALSE_RISK",
                    "severity": "medium",
                    "message": "Struktur-Modul meldete zuletzt FALSE_BREAKOUT.",
                    "evidence": {"event_id": str(ev.get("event_id", "")), "ts_ms": ev.get("ts_ms")},
                }
            )
            break

    rr = s.get("reward_risk_ratio")
    if rr is not None and float(rr) < settings.signal_min_reward_risk:
        out.append(
            {
                "code": "LOW_RR",
                "severity": "medium",
                "message": "Reward/Risk unter SIGNAL_MIN_REWARD_RISK.",
                "evidence": {"reward_risk_ratio": float(rr), "min": settings.signal_min_reward_risk},
            }
        )

    regime = str(s.get("market_regime") or "").strip().lower()
    if regime == "shock":
        out.append(
            {
                "code": "REGIME_SHOCK",
                "severity": "high",
                "message": "Regime-Klassifikator meldet Shock-Regime mit erhoehter Unsicherheit.",
                "evidence": {
                    "market_regime": s.get("market_regime"),
                    "regime_bias": s.get("regime_bias"),
                    "regime_confidence_0_1": s.get("regime_confidence_0_1"),
                },
            }
        )

    # News-Schock (gleiche Logik wie Rejection, evidenzbasiert; abschaltbar via ENV)
    news = inp.news_row
    if (
        settings.signal_news_shock_rejection_enabled
        and news
        and direction in ("long", "short")
    ):
        try:
            s_raw = news_sentiment_as_float(news.get("sentiment"))
            sent = float(s_raw or 0)
            rel = float(news.get("relevance_score") or 0)
        except (TypeError, ValueError):
            sent, rel = 0.0, 0.0
        if rel > 60 and sent < -0.35 and direction == "long":
            out.append(
                {
                    "code": "NEWS_SHOCK_AGAINST",
                    "severity": "high",
                    "message": "Hochrelevante News-Sentimentlage widerspricht Long.",
                    "evidence": {"relevance_score": rel, "sentiment": sent},
                }
            )
        elif rel > 60 and sent > 0.35 and direction == "short":
            out.append(
                {
                    "code": "NEWS_SHOCK_AGAINST",
                    "severity": "high",
                    "message": "Hochrelevante News-Sentimentlage widerspricht Short.",
                    "evidence": {"relevance_score": rel, "sentiment": sent},
                }
            )

    snap = s.get("source_snapshot_json")
    ug = snap.get("uncertainty_gate") if isinstance(snap, dict) else None
    if isinstance(ug, dict):
        phase = str(ug.get("gate_phase") or "")
        lane = ug.get("execution_lane")
        if phase == "blocked" or s.get("model_ood_alert"):
            out.append(
                {
                    "code": "UNCERTAINTY_OR_OOD_BLOCK",
                    "severity": "high",
                    "message": "Modell-Unsicherheit oder OOD: harte Abstinenz / keine Ausfuehrung.",
                    "evidence": {
                        "gate_phase": phase or None,
                        "model_uncertainty_0_1": s.get("model_uncertainty_0_1"),
                        "model_ood_score_0_1": s.get("model_ood_score_0_1"),
                        "model_ood_alert": s.get("model_ood_alert"),
                        "uncertainty_reasons_json": s.get("uncertainty_reasons_json") or [],
                        "ood_reasons_json": s.get("ood_reasons_json") or [],
                    },
                }
            )
        elif phase == "shadow_only" or lane == "shadow_only":
            out.append(
                {
                    "code": "UNCERTAINTY_SHADOW_LANE",
                    "severity": "medium",
                    "message": "Erhoehte Unsicherheit: nur Shadow/Paper, kein Live-Kandidat.",
                    "evidence": {
                        "gate_phase": phase,
                        "execution_lane": lane,
                        "lane_reasons_json": ug.get("lane_reasons_json") or [],
                        "model_uncertainty_0_1": s.get("model_uncertainty_0_1"),
                        "model_ood_score_0_1": s.get("model_ood_score_0_1"),
                    },
                }
            )
        elif phase == "minimal" or lane == "paper_only":
            out.append(
                {
                    "code": "UNCERTAINTY_MINIMAL_LANE",
                    "severity": "low",
                    "message": "Minimalfreigabe: Meta-Lane mindestens Paper (kein Live ohne Kandidat).",
                    "evidence": {
                        "gate_phase": phase,
                        "execution_lane": lane,
                        "lane_reasons_json": ug.get("lane_reasons_json") or [],
                        "model_uncertainty_0_1": s.get("model_uncertainty_0_1"),
                    },
                }
            )

    return out
