from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from signal_engine.config import SignalEngineSettings
from signal_engine.explain.risk_warnings import build_risk_warnings
from signal_engine.explain.schemas import ExplainInput
from signal_engine.explain import templates_de as T
from signal_engine.scoring.news_score import NEWS_LAYER_SENTIMENT_SCORE_CAP


def _explanation_schema_path() -> Path:
    here = Path(__file__).resolve()
    for d in here.parents:
        cand = d / "shared" / "contracts" / "schemas" / "signal_explanation.schema.json"
        if cand.is_file():
            return cand
    raise FileNotFoundError("shared/contracts/schemas/signal_explanation.schema.json nicht gefunden")


def _explanation_schema_validator() -> Draft202012Validator:
    path = _explanation_schema_path()
    with path.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


_SCHEMA_VALIDATOR: Draft202012Validator | None = None


def _get_validator() -> Draft202012Validator:
    global _SCHEMA_VALIDATOR
    if _SCHEMA_VALIDATOR is None:
        _SCHEMA_VALIDATOR = _explanation_schema_validator()
    return _SCHEMA_VALIDATOR


def build_short_de(inp: ExplainInput) -> str:
    s = inp.signal_row
    d = str(s.get("direction", "neutral"))
    strength = int(round(float(s.get("signal_strength_0_100", 0))))
    tf = str(s.get("timeframe", "?"))
    cls_ = str(s.get("signal_class", ""))
    dec = str(s.get("decision_state", ""))
    if d == "long":
        base = T.SHORT_LONG
    elif d == "short":
        base = T.SHORT_SHORT
    else:
        base = T.SHORT_NEUTRAL
    text = base.format(strength=strength, tf=tf)
    return f"{text} Klasse={cls_}, Entscheidung={dec}."


def _stop_mid(geo: dict[str, Any] | None) -> float | None:
    if geo is None:
        return None
    try:
        lo = float(geo["price_low"])
        hi = float(geo["price_high"])
        return (lo + hi) / 2.0
    except (KeyError, TypeError, ValueError):
        return None


def build_stop_explain_json(
    inp: ExplainInput,
    settings: SignalEngineSettings,
) -> dict[str, Any]:
    trigger = str(
        inp.signal_row.get("stop_trigger_type") or settings.signal_default_stop_trigger_type
    )
    if trigger == "mark_price":
        expl = T.STOP_MARK
    elif trigger == "fill_price":
        expl = T.STOP_FILL
    else:
        trigger = "unknown"
        expl = T.STOP_UNKNOWN
    stop_d = next((d for d in inp.drawings if d.get("type") == "stop_zone"), None)
    geo = stop_d.get("geometry") if stop_d else None
    return {
        "trigger_type": trigger,
        "trigger_explanation_de": expl,
        "stop_price_mid": _stop_mid(geo if isinstance(geo, dict) else None),
        "stop_zone_drawing_id": stop_d["drawing_id"] if stop_d else None,
        "basis": "active_stop_zone_drawing" if stop_d else "no_stop_drawing",
    }


def build_targets_explain_json(inp: ExplainInput) -> dict[str, Any]:
    targets = [d for d in inp.drawings if d.get("type") == "target_zone"]
    levels: list[dict[str, Any]] = []
    for i, d in enumerate(targets, start=1):
        g = d.get("geometry") or {}
        lo = g.get("price_low")
        hi = g.get("price_high")
        levels.append(
            {
                "rank": i,
                "drawing_id": d.get("drawing_id"),
                "price_low": str(lo) if lo is not None else None,
                "price_high": str(hi) if hi is not None else None,
                "rationale_de": (
                    f"Zielzone {i} aus Drawing-Engine (target_zone), "
                    f"horizontal_zone fuer naechstes Preisziel."
                ),
            }
        )
    return {"levels": levels, "count": len(levels)}


def _parse_json_obj(val: Any) -> dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _why_not_direction(inp: ExplainInput) -> dict[str, Any]:
    s = inp.signal_row
    d = str(s.get("direction", "neutral"))
    rj = _parse_json_obj(s.get("reasons_json"))
    rej = s.get("rejection_reasons_json") or []
    if isinstance(rej, str):
        rej = json.loads(rej)
    if not isinstance(rej, list):
        rej = []
    notes: list[str] = []
    if d == "neutral":
        notes.append("Richtung neutral: Struktur RANGE oder Gates (Struktur-/MTF-Score) nicht erfuellt.")
        notes.extend(rj.get("timeframe_notes", [])[:4])
    elif d == "long":
        notes.append("Short nicht gewaehlt: Struktur-Trend nicht DOWN bzw. Short-Gates nicht erfuellt.")
    else:
        notes.append("Long nicht gewaehlt: Struktur-Trend nicht UP bzw. Long-Gates nicht erfuellt.")
    return {
        "current_direction": d,
        "rejection_reasons": rej,
        "notes_de": notes,
    }


def _playbook_context_section(inp: ExplainInput) -> dict[str, Any]:
    s = inp.signal_row
    reasons_json = _parse_json_obj(s.get("reasons_json"))
    playbook = _parse_json_obj(reasons_json.get("playbook"))
    source_snapshot = _parse_json_obj(s.get("source_snapshot_json"))
    snapshot_ctx = _parse_json_obj(source_snapshot.get("playbook_context"))
    effective = snapshot_ctx or playbook
    decision_mode = (
        str(s.get("playbook_decision_mode") or effective.get("decision_mode") or "playbookless").strip()
    )
    benchmark_rule_ids = list(effective.get("benchmark_rule_ids") or [])
    counterfactuals = list(effective.get("counterfactual_candidates") or [])
    anti_patterns = list(effective.get("anti_pattern_hits") or [])
    blacklist_hits = list(effective.get("blacklist_hits") or [])
    invalid_context_hits = list(effective.get("invalid_context_hits") or [])
    return {
        "playbook_id": s.get("playbook_id") or effective.get("selected_playbook_id"),
        "playbook_family": s.get("playbook_family") or effective.get("selected_playbook_family"),
        "decision_mode": decision_mode,
        "registry_version": s.get("playbook_registry_version") or effective.get("registry_version"),
        "strategy_name": s.get("strategy_name") or effective.get("recommended_strategy_name"),
        "selection_reasons": list(effective.get("selection_reasons") or []),
        "benchmark_rule_ids": benchmark_rule_ids,
        "anti_pattern_hits": anti_patterns,
        "blacklist_hits": blacklist_hits,
        "invalid_context_hits": invalid_context_hits,
        "counterfactual_candidates": counterfactuals,
        "playbookless_reason": effective.get("playbookless_reason"),
        "summary_de": (
            "Entscheidung ist an ein registriertes Playbook gebunden."
            if decision_mode == "selected"
            else "Entscheidung bleibt bewusst playbook-los und muss explizit begruendet werden."
        ),
    }


def _regime_context_section(inp: ExplainInput) -> dict[str, Any]:
    s = inp.signal_row
    source_snapshot = _parse_json_obj(s.get("source_snapshot_json"))
    regime_snapshot = _parse_json_obj(source_snapshot.get("regime_snapshot"))
    transition_reasons = s.get("regime_transition_reasons_json") or []
    if isinstance(transition_reasons, str):
        try:
            transition_reasons = json.loads(transition_reasons)
        except json.JSONDecodeError:
            transition_reasons = []
    if not isinstance(transition_reasons, list):
        transition_reasons = []
    return {
        "market_regime": s.get("market_regime"),
        "regime_state": s.get("regime_state"),
        "regime_substate": s.get("regime_substate"),
        "regime_transition_state": s.get("regime_transition_state"),
        "regime_persistence_bars": s.get("regime_persistence_bars"),
        "regime_policy_version": s.get("regime_policy_version"),
        "regime_bias": s.get("regime_bias"),
        "regime_confidence_0_1": s.get("regime_confidence_0_1"),
        "regime_reasons_json": s.get("regime_reasons_json") or [],
        "regime_transition_reasons_json": transition_reasons,
        "regime_engine_version": regime_snapshot.get("regime_engine_version"),
        "regime_ontology_version": regime_snapshot.get("regime_ontology_version"),
        "raw_regime_state": regime_snapshot.get("raw_regime_state"),
        "pending_regime_state": regime_snapshot.get("pending_regime_state"),
        "market_family": regime_snapshot.get("market_family"),
        "canonical_instrument_id": regime_snapshot.get("canonical_instrument_id"),
        "summary_de": (
            "Regime ist family-aware klassifiziert; Uebergaenge sind hysterese-gebremst und auditierbar."
        ),
    }


def build_long_json(inp: ExplainInput, settings: SignalEngineSettings) -> dict[str, Any]:
    s = inp.signal_row
    st = inp.structure_state
    pf = inp.primary_feature
    rj = _parse_json_obj(s.get("reasons_json"))

    mtf_lines: list[str] = []
    for tf in ("1m", "5m", "15m", "1H", "4H"):
        row = inp.features_by_tf.get(tf)
        if row is None:
            mtf_lines.append(f"{tf}: keine Feature-Zeile")
        else:
            mtf_lines.append(f"{tf}: trend_dir={row.get('trend_dir')}")

    news_block: dict[str, Any] = {"available": False, "summary_de": "Keine News-Zeile in DB."}
    if inp.news_row:
        news_block = {
            "available": True,
            "relevance_score": inp.news_row.get("relevance_score"),
            "sentiment": inp.news_row.get("sentiment"),
            "title": inp.news_row.get("title"),
            "summary_de": "News aus app.news_items (ohne Inhaltsinterpretation).",
        }

    payload = {
        "schema_version": "1.0",
        "signal_id": str(s.get("signal_id", "")),
        "symbol": str(s.get("symbol", "")),
        "timeframe": str(s.get("timeframe", "")),
        "explain_version": settings.signal_explain_version,
        "sections": {
            "market_structure": {
                "trend_dir": st.get("trend_dir") if st else None,
                "compression_flag": st.get("compression_flag") if st else None,
                "structure_score": s.get("structure_score_0_100"),
                "notes": rj.get("structural_notes", []),
            },
            "momentum": {
                "momentum_score_layer": s.get("momentum_score_0_100"),
                "rsi_14": pf.get("rsi_14") if pf else None,
                "ret_1": pf.get("ret_1") if pf else None,
                "notes": rj.get("momentum_notes", []),
            },
            "multi_timeframe": {
                "multi_timeframe_score": s.get("multi_timeframe_score_0_100"),
                "per_timeframe_lines": mtf_lines,
                "notes": rj.get("timeframe_notes", []),
            },
            "news_context": news_block,
            "risk_and_stop": {
                "risk_score": s.get("risk_score_0_100"),
                "reward_risk_ratio": s.get("reward_risk_ratio"),
                "decision_state": s.get("decision_state"),
                "notes": rj.get("risk_notes", []),
                "stop_budget_policy_version": s.get("stop_budget_policy_version"),
                "stop_distance_pct": s.get("stop_distance_pct"),
                "stop_budget_max_pct_allowed": s.get("stop_budget_max_pct_allowed"),
                "stop_min_executable_pct": s.get("stop_min_executable_pct"),
                "stop_to_spread_ratio": s.get("stop_to_spread_ratio"),
                "stop_quality_0_1": s.get("stop_quality_0_1"),
                "stop_executability_0_1": s.get("stop_executability_0_1"),
                "stop_fragility_0_1": s.get("stop_fragility_0_1"),
                "stop_budget_assessment": rj.get("stop_budget_assessment")
                if isinstance(rj.get("stop_budget_assessment"), dict)
                else None,
            },
            "targets": {
                "target_drawing_ids": s.get("target_zone_ids_json", []),
                "detail": build_targets_explain_json(inp),
            },
            "regime_context": _regime_context_section(inp),
            "playbook_context": _playbook_context_section(inp),
            "uncertainty_breakdown": _uncertainty_breakdown_section(inp),
            "why_not_direction": _why_not_direction(inp),
            "decision_pipeline": _decision_pipeline_section(inp, rj),
            "peripheral_boundary": _peripheral_boundary_section(s, rj),
        },
    }
    _get_validator().validate(payload)
    return payload


def _uncertainty_breakdown_section(inp: ExplainInput) -> dict[str, Any]:
    s = inp.signal_row
    snap = s.get("source_snapshot_json")
    snap = snap if isinstance(snap, dict) else {}
    ua = snap.get("uncertainty_assessment")
    ua = ua if isinstance(ua, dict) else {}
    rj = _parse_json_obj(s.get("reasons_json"))
    comp = rj.get("uncertainty_components") if isinstance(rj.get("uncertainty_components"), dict) else {}
    return {
        "policy_version": ua.get("policy_version"),
        "aggregate_0_1": s.get("model_uncertainty_0_1"),
        "effective_for_leverage_0_1": s.get("uncertainty_effective_for_leverage_0_1"),
        "components_v2": ua.get("components_v2") or comp,
        "monitoring_hooks": ua.get("monitoring_hooks"),
        "exit_execution_bias": rj.get("uncertainty_exit_execution_bias"),
        "top_reasons": (s.get("uncertainty_reasons_json") or [])[:12],
    }


def _decision_pipeline_section(
    inp: ExplainInput,
    reasons_json: dict[str, Any],
) -> dict[str, Any]:
    signal_row = inp.signal_row
    dcf = reasons_json.get("decision_control_flow")
    if not isinstance(dcf, dict):
        dcf = {}
    lines: list[str] = []
    phases_structured: list[dict[str, Any]] = []
    for p in dcf.get("phases") or []:
        if not isinstance(p, dict):
            continue
        o = p.get("order")
        t = p.get("title_de")
        out = p.get("outcome")
        n = p.get("notes_de") or ""
        lines.append(f"{o}. {t} — Ergebnis: {out}. {n}")
        ev = p.get("evidence")
        ev_keys = sorted(ev.keys()) if isinstance(ev, dict) else []
        phases_structured.append(
            {
                "id": p.get("id"),
                "order": o,
                "outcome": out,
                "evidence_keys": ev_keys,
            }
        )
    ntp = dcf.get("no_trade_path") if isinstance(dcf.get("no_trade_path"), dict) else {}
    edb = dcf.get("end_decision_binding") if isinstance(dcf.get("end_decision_binding"), dict) else {}
    out: dict[str, Any] = {
        "pipeline_version": dcf.get("pipeline_version"),
        "ordered_phases_de": lines,
        "phases_structured": phases_structured,
        "final_summary": dcf.get("final_summary"),
        "end_decision_binding": edb,
        "no_trade_path": ntp,
        "raw_phase_ids": [p.get("id") for p in (dcf.get("phases") or []) if isinstance(p, dict)],
    }
    fm = inp.foundation_model_tsfm
    if not fm:
        snap = signal_row.get("source_snapshot_json")
        if isinstance(snap, dict) and isinstance(snap.get("foundation_model_tsfm"), dict):
            fm = snap["foundation_model_tsfm"]
    if isinstance(fm, dict) and fm:
        out["foundation_model_tsfm"] = fm
    return out


def _peripheral_boundary_section(
    signal_row: dict[str, Any],
    reasons_json: dict[str, Any],
) -> dict[str, Any]:
    dcf = reasons_json.get("decision_control_flow")
    boundary = (
        dcf.get("peripheral_boundary_de")
        if isinstance(dcf, dict)
        else None
    ) or (
        "News und externe Textquellen sind randstaendig: nur Layer-4-Score und explizite "
        "deterministische Reject-Regeln. Kein LLM in der Signal-Engine-Kernentscheidung."
    )
    return {
        "statement_de": boundary,
        "news_layer": {
            "role_de": "Nur Gewicht im Composite und optionale News-Shock-Reject-Regeln.",
            "max_abs_sentiment_score_adjustment": NEWS_LAYER_SENTIMENT_SCORE_CAP,
        },
        "llm_core_pipeline_de": "Kein LLM-Aufruf in Scoring, Hybrid oder Meta-Labeling der Signal-Engine.",
    }


def build_long_md_de(
    inp: ExplainInput,
    long_json: dict[str, Any],
    risk_warnings: list[dict[str, Any]],
    stop_explain: dict[str, Any],
) -> str:
    s = inp.signal_row
    lines: list[str] = []
    sid = s.get("signal_id", "")
    lines.append(f"# Signal-Erklaerung ({sid})")
    lines.append("")
    lines.append(
        f"**Richtung:** `{s.get('direction')}` | **Staerke:** {s.get('signal_strength_0_100')}/100 "
        f"| **Wahrscheinlichkeit:** {s.get('probability_0_1')} | **Klasse:** `{s.get('signal_class')}`"
    )
    lines.append("")
    lines.append("## Marktstruktur")
    sec = long_json["sections"]["market_structure"]
    lines.append(f"- Trend (structure_state): `{sec.get('trend_dir')}`")
    lines.append(f"- Kompression: `{sec.get('compression_flag')}`")
    lines.append(f"- Struktur-Score: `{sec.get('structure_score')}`")
    for n in sec.get("notes", [])[:8]:
        lines.append(f"  - {n}")
    lines.append("")
    lines.append("## Momentum")
    sec = long_json["sections"]["momentum"]
    lines.append(f"- Momentum-Score (Schicht): `{sec.get('momentum_score_layer')}`")
    lines.append(f"- RSI(14): `{sec.get('rsi_14')}` | ret_1: `{sec.get('ret_1')}`")
    for n in sec.get("notes", [])[:8]:
        lines.append(f"  - {n}")
    lines.append("")
    lines.append("## Multi-Timeframe")
    sec = long_json["sections"]["multi_timeframe"]
    lines.append(f"- MTF-Score: `{sec.get('multi_timeframe_score')}`")
    for l in sec.get("per_timeframe_lines", []):
        lines.append(f"  - {l}")
    lines.append("")
    lines.append("## News-Kontext")
    nc = long_json["sections"]["news_context"]
    lines.append(f"- Verfuegbar: `{nc.get('available')}`")
    lines.append(f"- {nc.get('summary_de')}")
    if nc.get("title"):
        lines.append(f"- Titel (Fakt): {nc.get('title')}")
    lines.append("")
    lines.append("## Risiko & Stop")
    rs = long_json["sections"]["risk_and_stop"]
    lines.append(f"- Risiko-Score: `{rs.get('risk_score')}` | RR: `{rs.get('reward_risk_ratio')}`")
    lines.append(f"- Entscheidung: `{rs.get('decision_state')}`")
    lines.append(
        f"- Stop trigger_type: `{stop_explain.get('trigger_type')}` — "
        f"{stop_explain.get('trigger_explanation_de')}"
    )
    lines.append(f"- Stop-Preis (Mitte Zone): `{stop_explain.get('stop_price_mid')}`")
    lines.append("")
    lines.append("### Risiko-Warnungen (regelbasiert)")
    for w in risk_warnings:
        lines.append(
            f"- **{w.get('code')}** ({w.get('severity')}): {w.get('message')}"
        )
    lines.append("")
    ub = long_json["sections"].get("uncertainty_breakdown") or {}
    if ub.get("aggregate_0_1") is not None or ub.get("components_v2"):
        lines.append("## Mehrdimensionale Unsicherheit")
        lines.append(
            f"- Policy: `{ub.get('policy_version')}` | Aggregat: `{ub.get('aggregate_0_1')}` | "
            f"Leverage-Eingang: `{ub.get('effective_for_leverage_0_1')}`"
        )
        cv = ub.get("components_v2") or {}
        if isinstance(cv, dict) and cv:
            lines.append(
                f"- Daten: `{cv.get('data_uncertainty_0_1')}` | Regime: `{cv.get('regime_uncertainty_0_1')}` | "
                f"Execution: `{cv.get('execution_uncertainty_0_1')}` | Modell: `{cv.get('model_uncertainty_pure_0_1')}` | "
                f"Policy: `{cv.get('policy_uncertainty_0_1')}`"
            )
        if ub.get("exit_execution_bias"):
            lines.append(f"- Exit-Bias: `{ub.get('exit_execution_bias')}`")
        mh = ub.get("monitoring_hooks") or {}
        if isinstance(mh, dict) and any(mh.values()):
            lines.append(f"- Monitoring: `{mh}`")
        for tr in ub.get("top_reasons") or []:
            lines.append(f"  - {tr}")
        lines.append("")
    lines.append("## Targets (gestuft)")
    tgt = long_json["sections"]["targets"].get("detail") or {}
    for lev in tgt.get("levels", []):
        lines.append(
            f"- Stufe {lev.get('rank')}: {lev.get('price_low')} … {lev.get('price_high')} "
            f"(drawing_id={lev.get('drawing_id')})"
        )
        lines.append(f"  - {lev.get('rationale_de')}")
    lines.append("")
    lines.append("## Regime-Kontext")
    rg = long_json["sections"].get("regime_context") or {}
    lines.append(
        f"- Grobregime: `{rg.get('market_regime')}` | State: `{rg.get('regime_state')}` "
        f"| Substate: `{rg.get('regime_substate')}`"
    )
    lines.append(
        f"- Transition: `{rg.get('regime_transition_state')}` | Persistenz (Bars): "
        f"`{rg.get('regime_persistence_bars')}` | Policy: `{rg.get('regime_policy_version')}`"
    )
    lines.append(
        f"- Bias: `{rg.get('regime_bias')}` | Konfidenz: `{rg.get('regime_confidence_0_1')}`"
    )
    if rg.get("regime_engine_version") or rg.get("regime_ontology_version"):
        lines.append(
            f"- Engine: `{rg.get('regime_engine_version')}` | Ontologie: `{rg.get('regime_ontology_version')}`"
        )
    if rg.get("raw_regime_state") or rg.get("pending_regime_state"):
        lines.append(
            f"- Rohkandidat: `{rg.get('raw_regime_state')}` | Pending: `{rg.get('pending_regime_state')}`"
        )
    if rg.get("canonical_instrument_id") or rg.get("market_family"):
        lines.append(
            f"- Instrument: `{rg.get('canonical_instrument_id')}` | Familie: `{rg.get('market_family')}`"
        )
    lines.append(f"- {rg.get('summary_de')}")
    if rg.get("regime_transition_reasons_json"):
        lines.append("- Uebergangsgruende:")
        for item in rg.get("regime_transition_reasons_json", [])[:10]:
            lines.append(f"  - {item}")
    if rg.get("regime_reasons_json"):
        lines.append("- Regime-Fakten (Top):")
        for item in rg.get("regime_reasons_json", [])[:10]:
            lines.append(f"  - {item}")
    lines.append("")
    lines.append("## Playbook-Kontext")
    pb = long_json["sections"].get("playbook_context") or {}
    lines.append(
        f"- Modus: `{pb.get('decision_mode')}` | Playbook: `{pb.get('playbook_id')}` "
        f"| Familie: `{pb.get('playbook_family')}`"
    )
    if pb.get("strategy_name"):
        lines.append(f"- Bevorzugte Strategie-Familie: `{pb.get('strategy_name')}`")
    lines.append(f"- {pb.get('summary_de')}")
    if pb.get("selection_reasons"):
        lines.append("- Auswahlgruende:")
        for item in pb.get("selection_reasons", [])[:8]:
            lines.append(f"  - {item}")
    if pb.get("benchmark_rule_ids"):
        lines.append("- Benchmark-Regeln:")
        for item in pb.get("benchmark_rule_ids", [])[:8]:
            lines.append(f"  - {item}")
    if pb.get("anti_pattern_hits"):
        lines.append("- Anti-Pattern-Treffer:")
        for item in pb.get("anti_pattern_hits", [])[:8]:
            lines.append(f"  - {item}")
    if pb.get("blacklist_hits"):
        lines.append("- Blacklist-Treffer:")
        for item in pb.get("blacklist_hits", [])[:8]:
            lines.append(f"  - {item}")
    if pb.get("counterfactual_candidates"):
        lines.append("- Counterfactual-Kandidaten:")
        for item in pb.get("counterfactual_candidates", [])[:5]:
            lines.append(f"  - {item}")
    if pb.get("playbookless_reason"):
        lines.append(f"- Playbook-los-Begruendung: {pb.get('playbookless_reason')}")
    lines.append("")
    lines.append("## Warum nicht Long/Short? (Konfliktanalyse)")
    wnd = long_json["sections"]["why_not_direction"]
    for n in wnd.get("notes_de", []):
        lines.append(f"- {n}")
    if wnd.get("rejection_reasons"):
        lines.append("- Ablehnungs-/Downgrade-Gruende (Fakten aus rejection_reasons_json):")
        for item in wnd["rejection_reasons"][:12]:
            if isinstance(item, str):
                lines.append(f"  - {item}")
            else:
                lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
    lines.append("")
    lines.append("## Endentscheid (Pipeline-Reihenfolge)")
    dp = long_json["sections"].get("decision_pipeline") or {}
    lines.append(f"- Pipeline-Version: `{dp.get('pipeline_version')}`")
    for row in dp.get("ordered_phases_de") or []:
        lines.append(f"- {row}")
    fs = dp.get("final_summary") or {}
    lines.append(
        f"- **Endzustand:** trade_action=`{fs.get('trade_action')}`, "
        f"meta_lane=`{fs.get('meta_trade_lane')}`, state=`{fs.get('decision_state')}`"
    )
    edb = dp.get("end_decision_binding") or {}
    if edb:
        lines.append("- **Gebundene Ausfuehrung (Playbook/Exits/Stops/Hebel-Hints):**")
        lines.append(
            f"  - Playbook: `{edb.get('playbook_id')}` / Familie `{edb.get('playbook_family')}` "
            f"(Modus `{edb.get('playbook_decision_mode')}`)"
        )
        lines.append(
            f"  - Exit primaer (Ensemble): `{edb.get('exit_family_primary')}` | "
            f"effektiv: `{edb.get('exit_family_effective_primary')}` | "
            f"Stop-Budget(0..1): `{edb.get('stop_budget_0_1')}`"
        )
        eff_ranked = edb.get("exit_families_effective_ranked") or []
        if eff_ranked:
            lines.append(f"  - Exit-Familien effektiv (Top): `{', '.join(str(x) for x in eff_ranked[:6])}`")
        drv = edb.get("exit_resolution_drivers") or []
        if drv:
            lines.append(f"  - Exit-Aufloesung Treiber: `{', '.join(str(x) for x in drv[:8])}`")
        lbf = edb.get("leverage_band_fraction_0_1") or {}
        lines.append(
            f"  - Hebel-Band (Anteil Engine-Cap): min `{lbf.get('min')}` max `{lbf.get('max')}` | "
            f"allowed=`{edb.get('allowed_leverage')}` rec=`{edb.get('recommended_leverage')}`"
        )
    ntp = dp.get("no_trade_path") or {}
    if ntp.get("no_trade_is_final_outcome"):
        lines.append("- **No-Trade-Pfad (auditierbar):**")
        if ntp.get("policy_de"):
            lines.append(f"  - {ntp.get('policy_de')}")
        for d in (ntp.get("phase_block_drivers") or [])[:8]:
            if isinstance(d, dict):
                lines.append(
                    f"  - Phase `{d.get('phase_id')}` → `{d.get('outcome')}`: {d.get('notes_de') or ''}"
                )
        for tag in (ntp.get("abstention_reasons_top") or [])[:10]:
            lines.append(f"  - Abstention: `{tag}`")
    fm = dp.get("foundation_model_tsfm")
    if isinstance(fm, dict) and fm.get("summary_de"):
        lines.append("")
        lines.append("### Foundation Model (TimesFM)")
        lines.append(f"- {fm.get('summary_de')}")
        if fm.get("model_id"):
            lines.append(f"- Modell: `{fm.get('model_id')}`")
        if fm.get("confidence_0_1") is not None:
            lines.append(f"- Modell-Konfidenz (0..1): `{fm.get('confidence_0_1')}`")
    lines.append("")
    lines.append("## Randkomponenten (News / LLM-Grenze)")
    pb = long_json["sections"].get("peripheral_boundary") or {}
    lines.append(f"- {pb.get('statement_de')}")
    lines.append(f"- {pb.get('llm_core_pipeline_de')}")
    nl = pb.get("news_layer") or {}
    lines.append(
        f"- News-Layer: {nl.get('role_de')} "
        f"(max. Score-Verschiebung durch Sentiment: ±{nl.get('max_abs_sentiment_score_adjustment')})"
    )
    return "\n".join(lines)


def build_explanation_bundle(
    inp: ExplainInput,
    settings: SignalEngineSettings,
) -> dict[str, Any]:
    """Deterministisches Paket fuer DB-Spalten app.signal_explanations."""
    risk = build_risk_warnings(inp, settings)
    stop_explain = build_stop_explain_json(inp, settings)
    targets_explain = build_targets_explain_json(inp)
    long_json = build_long_json(inp, settings)
    long_md = build_long_md_de(inp, long_json, risk, stop_explain)
    short = build_short_de(inp)
    return {
        "explain_version": settings.signal_explain_version,
        "explain_short": short,
        "explain_long_md": long_md,
        "explain_long_json": long_json,
        "risk_warnings_json": risk,
        "stop_explain_json": stop_explain,
        "targets_explain_json": targets_explain,
    }
