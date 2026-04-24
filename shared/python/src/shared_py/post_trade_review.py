"""
Post-Trade-Review (Schema post_trade_review v1) und AI-Reasoning-Attribution.

Verknuepft KI-Szenario (strategy_signal_explain) mit Kerzenfenster (z. B. 4h) und P&L,
um „Lucky Trade / Wrong Reasoning“ u. a. zu markieren.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, Literal

PostTradeReviewV1 = dict[str, Any]

QualityLabel = Literal[
    "sound_reasoning_win",
    "lucky_wrong_reasoning",
    "sound_thesis_bad_outcome",
    "failed_thesis_loss",
    "inconclusive",
]


def _dec(x: Any) -> Decimal:
    return Decimal(str(x))


def extract_reference_level_from_strategy_result(
    result: dict[str, Any] | None,
) -> tuple[float | None, str, Literal["support", "resistance", "unknown"]]:
    """
    Liefert (preis, quelle, rolle). Prioritaet: chart_annotations, dann Szenario-Text.
    """
    if not isinstance(result, dict):
        return None, "missing_result", "unknown"
    ex = (result.get("expected_scenario_de") or "").strip()
    if isinstance(ex, str) and ex:
        el = ex.lower()
        m = re.findall(
            r"\b(\d{1,2})[kK]\b|\b(\d{4,6}(?:[.,]\d+)?)\b",
            ex,
        )
        prices: list[float] = []
        for a, b in m[:8]:
            try:
                if a:
                    prices.append(float(a) * 1000.0)
                elif b:
                    prices.append(float(b.replace(",", ".")))
            except (TypeError, ValueError):
                continue
        if prices:
            p = min(prices) if "support" in el or "long" in el else max(prices)
            role: Literal["support", "resistance", "unknown"] = (
                "resistance"
                if "resist" in el or "widerstand" in el or "short" in el
                else "support"
            )
            return p, "expected_scenario_de", role

    ca = result.get("chart_annotations")
    if not isinstance(ca, dict):
        return None, "no_chart_annotations", "unknown"

    levels: list[float] = []
    for hl in ca.get("horizontal_lines") or []:
        if isinstance(hl, dict) and hl.get("price") is not None:
            try:
                levels.append(float(hl["price"]))
            except (TypeError, ValueError):
                continue
    for pb in ca.get("price_bands") or []:
        if isinstance(pb, dict):
            for k in ("price_low", "price_high"):
                if pb.get(k) is not None:
                    try:
                        levels.append(float(pb[k]))
                    except (TypeError, ValueError):
                        continue
    if not levels:
        return None, "no_numeric_levels", "unknown"

    lbl = " ".join(
        str(x.get("label") or "")
        for x in (ca.get("horizontal_lines") or [])[:6]
        if isinstance(x, dict)
    ).lower()
    if "resist" in lbl or "widerstand" in lbl:
        return max(levels), "chart_annotations", "resistance"
    if "support" in lbl or "unterst" in lbl:
        return min(levels), "chart_annotations", "support"
    return min(levels), "chart_annotations", "support"


def evaluate_thesis_vs_candles(
    *,
    side: str,
    reference_price: float,
    role: Literal["support", "resistance", "unknown"],
    candles: list[dict[str, Any]],
    relax_pct: float = 0.0025,
) -> tuple[bool, dict[str, Any]]:
    """
    Prueft, ob im Fenster der Support/Resistance „gehalten“ wurde (heuristisch).
    long + support: min(low) >= ref * (1 - relax)
    short + resistance: max(high) <= ref * (1 + relax)
    """
    if not candles or reference_price <= 0:
        return False, {"error": "no_candles_or_price"}
    lows = [float(c["low"]) for c in candles if c.get("low") is not None]
    highs = [float(c["high"]) for c in candles if c.get("high") is not None]
    if not lows or not highs:
        return False, {"error": "ohlc_incomplete"}
    mn, mx = min(lows), max(highs)
    s = side.lower()
    r = role if role != "unknown" else ("support" if s == "long" else "resistance")
    if s == "long" and r == "support":
        held = mn >= reference_price * (1.0 - relax_pct)
    elif s == "short" and r == "resistance":
        held = mx <= reference_price * (1.0 + relax_pct)
    elif s == "long":
        held = mn >= reference_price * (1.0 - relax_pct)
    else:
        held = mx <= reference_price * (1.0 + relax_pct)
    return held, {
        "min_low": mn,
        "max_high": mx,
        "reference_price": reference_price,
        "role": r,
        "relax_pct": relax_pct,
    }


def classify_reasoning_quality(
    *,
    pnl_net: Decimal,
    thesis_holds: bool | None,
) -> tuple[QualityLabel, float]:
    """
    reasoning_accuracy: grobe Kalibrierung 0..1 (Logik vs. Markt, nicht nur P&L).
    """
    win = pnl_net > 0
    if thesis_holds is None:
        return "inconclusive", 0.5
    if win and thesis_holds:
        return "sound_reasoning_win", 0.95
    if win and not thesis_holds:
        return "lucky_wrong_reasoning", 0.12
    if not win and thesis_holds:
        return "sound_thesis_bad_outcome", 0.58
    return "failed_thesis_loss", 0.05


def build_post_trade_review_v1(
    *,
    outcome_summary_de: str,
    lessons_de: list[str],
    what_worked_de: str,
    what_failed_de: str,
    bias_check_de: str,
    review_confidence_0_1: float,
) -> PostTradeReviewV1:
    return {
        "schema_version": "1.0",
        "outcome_vs_plan_de": outcome_summary_de,
        "lessons_de": lessons_de,
        "what_worked_de": what_worked_de,
        "what_failed_de": what_failed_de,
        "bias_check_de": bias_check_de,
        "review_confidence_0_1": max(0.0, min(1.0, float(review_confidence_0_1))),
    }


def build_attribution_post_trade_review(
    *,
    quality_label: QualityLabel,
    pnl_net: Decimal,
    scenario_excerpt: str,
    thesis_holds: bool | None,
    meta: dict[str, Any],
) -> PostTradeReviewV1:
    """Befuellt PostTradeReviewV1 aus deterministischer Attribution."""
    th = "unbekannt (kein Referenzpreis/Szenario)"
    if thesis_holds is True:
        th = "Szenario/Level im 4h-Fenster stimmig mit KI-Beschreibung ueberein."
    elif thesis_holds is False:
        th = "Szenario/Level im 4h-Fenster widerspricht der KI-Erwartung (Preis brach)."

    if quality_label == "lucky_wrong_reasoning":
        lessons = [
            "Trade im Plus, aber Begruendung/Szenario passt nicht zum Preisverlauf — "
            "Attribution: Glueck / falsche Begruendung.",
        ]
        worked = (
            "Disziplin bei Exit/Size kann trotzdem greifen — "
            "pruefe unabhaengig von der KI-Story."
        )
        failed = (
            "KI-Szenario und Chart-Level wichen ab; "
            "nicht als validierte These werten."
        )
        bias = "Gewinner-Trades nicht automatisch als „KI lag richtig“ buchen."
        out = (
            f"P&L {pnl_net} USDT; {th} "
            f"Label={quality_label} (Reasoning-Accuracy niedrig trotz Gewinn)."
        )
        conf = 0.55
    elif quality_label == "sound_reasoning_win":
        lessons = [
            "Szenario und P&L passen — gueter Kandidat fuer Modellvertrauen.",
        ]
        worked = "KernThese und Marktverlauf im Fenster waren konsistent."
        failed = "—"
        bias = "Weiter beobachten; ein Treffer beweist kein generelles Ueberstehen."
        out = f"P&L {pnl_net} USDT; {th} Label={quality_label}."
        conf = 0.72
    elif quality_label == "failed_thesis_loss":
        lessons = [
            "Verlust und widerlegte Erwartung — KI-Story und Abgleich hart pruefen.",
        ]
        worked = "Risikomanagement (Stopp) falls aktiv."
        failed = "P&L negativ und Level/Szenario im Fenster widerspricht der Story."
        bias = "Nicht narrativ recht fertig machen: Messung wiederholen."
        out = f"P&L {pnl_net} USDT; {th} Label={quality_label}."
        conf = 0.65
    elif quality_label == "sound_thesis_bad_outcome":
        lessons = [
            "These plausibel, Outcome negativ — Slippage/Timing/Ereignis pruefen.",
        ]
        worked = "Narrative stimmte grob mit Preisverlauf ueberein."
        failed = "P&L trotzdem negativ; Exit-Logik separat bewerten."
        bias = "Nicht sofort KI-These verwefen."
        out = f"P&L {pnl_net} USDT; {th} Label={quality_label}."
        conf = 0.5
    else:
        lessons = [
            f"Szenario-Auszug: {scenario_excerpt[:200]}",
        ]
        worked = "—"
        failed = "Kein belastbarer Abgleich (fehlende Levels oder Kerzen)."
        bias = "Weder Glueck noch Kompetenz ableitbar."
        out = f"P&L {pnl_net} USDT; Attribution unklar. meta={list(meta.keys())[:6]}"
        conf = 0.35

    return build_post_trade_review_v1(
        outcome_summary_de=out,
        lessons_de=lessons,
        what_worked_de=worked,
        what_failed_de=failed,
        bias_check_de=bias,
        review_confidence_0_1=conf,
    )
