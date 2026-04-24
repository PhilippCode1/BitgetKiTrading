"""Numerischer TimesFM-Patch -> semantische Kurzbeurteilung (ohne LLM, <20ms)."""

from __future__ import annotations

from llm_orchestrator.agents.tsfm_types import TsfmSemanticSynthesis, TsfmSignalCandidatePayloadV1

# Operator-/War-Room-Prompt: fehlende Marktdaten ehrlich benennen (mit Prompt-Manifest)
OPERATOR_MARKET_DATA_GAP_DIRECTIVE_DE = (
    "Falls in READONLY_KONTEXT explizit Hinweise wie leeres Orderbook oder "
    "\"[KEINE AKTUELLEN NEWS VERFÜGBAR]\" o. ae. vorkommen: weise in der Antwort sichtbar "
    "darauf hin, dass diese Marktdaten fuer die Einschätzung fehlten — "
    "erfinde sie nicht und halluziniere keine Preis-/Buch-Details."
)


def synthesize_tsfm_signal(tsfm: TsfmSignalCandidatePayloadV1) -> TsfmSemanticSynthesis:
    pv = tsfm.forecast_preview
    h = int(tsfm.forecast_horizon)
    if len(pv) >= 2:
        d0, d1 = float(pv[0]), float(pv[-1])
        slope = (d1 - d0) / max(1e-12, abs(d0))
    elif len(pv) == 1:
        slope = 0.0
    else:
        slope = 0.0
    gap_note = ""
    if not pv:
        gap_note = (
            "Hinweis: Kein Forecast-Preview in den Eingabedaten — semantische Schicht reduziert, "
            "keine Richtung aus dem Patch ableitbar. "
        )
    if slope > 0.0008:
        bias = "long"
    elif slope < -0.0008:
        bias = "short"
    else:
        bias = "neutral"
    mr = float(min(1.0, max(0.0, tsfm.patch_incr_std * 120.0)))
    base_c = float(tsfm.confidence_0_1)
    syn_c = max(0.05, min(0.99, base_c * (0.92 if bias == "neutral" else 1.0)))
    ticks = min(100, max(30, h))
    if bias == "long":
        trend_de = "aufwaertsgerichteter Erwartungspfad"
    elif bias == "short":
        trend_de = "abwaertsgerichteter Erwartungspfad"
    else:
        trend_de = "seitwaerts / Mean-Reversion-naehe"
    if mr >= 0.55:
        mr_phrase = (
            f"Starker Mean-Reversion-Impuls innerhalb der naechsten ca. {ticks} Ticks "
            f"mit {syn_c:.0%} semantischer Ueberzeugung (Modell-Rohkonfidenz {base_c:.0%})."
        )
    else:
        mr_phrase = (
            f"Moderater Mean-Reversion-Impuls (Score {mr:.0%}) im Horizont ~{ticks} Ticks; "
            f"semantische Sicherheit {syn_c:.0%} (Rohkonfidenz {base_c:.0%})."
        )
    narrative = (
        f"{gap_note}"
        f"Zero-Shot Pattern Recognition des Foundation Models ({tsfm.model_id or 'timesfm'}): "
        f"{trend_de}. {mr_phrase} "
        f"Richtungstendenz: {('Long' if bias == 'long' else 'Short' if bias == 'short' else 'Neutral')}."
    )
    return TsfmSemanticSynthesis(
        narrative_de=narrative,
        directional_bias=bias,
        synthesis_confidence_0_1=syn_c,
        mean_reversion_score_0_1=mr,
        horizon_ticks=ticks,
    )
