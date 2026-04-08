"""
Deterministische Aufloesung der Exit-Familien-Reihenfolge fuer Audit, Learning und Ausfuehrungs-Hints.

Quellen: Ensemble-Binding (Spezialisten), Playbook-Kontext, MFE/MAE-Projektion, Microstructure,
Funding/Basis (Futures), News-Score. Keine LLMs.
"""

from __future__ import annotations

import json
from typing import Any, get_args

from shared_py.playbook_registry import PlaybookExitFamily

EXIT_FAMILY_RESOLUTION_VERSION = "exit-family-resolution-v1"

_LEGACY_EXIT_ALIASES: dict[str, str] = {
    "adaptive_scale_runner": "trend_follow_runner",
}

_VALID_EXIT_FAMILIES: frozenset[str] = frozenset(get_args(PlaybookExitFamily))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_family(name: str) -> str:
    s = str(name or "").strip()
    return _LEGACY_EXIT_ALIASES.get(s, s)


def _primary_microstructure(db_row: dict[str, Any]) -> dict[str, Any]:
    snap = _as_dict(db_row.get("source_snapshot_json"))
    fs = snap.get("feature_snapshot")
    if not isinstance(fs, dict):
        return {}
    primary = fs.get("primary_tf")
    if isinstance(primary, dict):
        return primary
    ptf = str(fs.get("primary_timeframe") or "").strip()
    tfs = fs.get("timeframes")
    if isinstance(tfs, dict) and ptf:
        block = tfs.get(ptf)
        if isinstance(block, dict):
            return block
    return {}


def _news_score(db_row: dict[str, Any]) -> float | None:
    v = _coerce_float(db_row.get("news_score_0_100"))
    if v is not None:
        return v
    snap = _as_dict(db_row.get("source_snapshot_json"))
    return _coerce_float(snap.get("news_score_0_100"))


def _take_pct_profile_from_ranked(ranked: list[str]) -> str:
    head = set(ranked[:4])
    if "news_risk_flatten" in head or "event_exit" in head:
        return "flatten_fast"
    if "trend_follow_runner" in head or ("runner" in head and "trend_hold" in head):
        return "runner_heavy"
    if "mean_reversion_snapback" in head or "mean_reversion_unwind" in head:
        return "early_scale"
    if "liquidity_target" in head:
        return "liquidity_skim"
    if "funding_harvest" in head or "basis_funding_unwind" in head:
        return "funding_skew"
    if "time_stop" in head and len(head & {"scale_out", "runner", "trend_hold"}) == 0:
        return "time_biased"
    return "balanced"


def _execution_hints(
    *,
    ranked: list[str],
    drivers: list[str],
    take_pct_profile: str,
) -> dict[str, Any]:
    profile = take_pct_profile
    runner_enabled: bool | None = None
    runner_arm_after_tp_index: int | None = None
    break_even_after_tp_index: int | None = None

    if profile == "flatten_fast":
        runner_enabled = False
        runner_arm_after_tp_index = None
        break_even_after_tp_index = 0
    elif profile == "runner_heavy":
        runner_enabled = True
        runner_arm_after_tp_index = 1
        break_even_after_tp_index = 1
    elif profile == "early_scale":
        runner_enabled = True
        runner_arm_after_tp_index = 0
        break_even_after_tp_index = 0
    elif profile == "liquidity_skim":
        runner_enabled = True
        runner_arm_after_tp_index = 1
        break_even_after_tp_index = 0
    elif profile == "funding_skew":
        runner_enabled = True
        runner_arm_after_tp_index = 1
        break_even_after_tp_index = 1
    elif profile == "time_biased":
        runner_enabled = False
        break_even_after_tp_index = 0

    return {
        "take_pct_profile": profile,
        "runner_enabled": runner_enabled,
        "runner_arm_after_tp_index": runner_arm_after_tp_index,
        "break_even_after_tp_index": break_even_after_tp_index,
        "ranked_head": ranked[:4],
        "drivers": list(drivers),
    }


def resolve_exit_family_resolution(
    *,
    db_row: dict[str, Any],
    end_decision_binding: dict[str, Any],
) -> dict[str, Any]:
    """
    Erzeugt kanonische Exit-Aufloesung inkl. effektiver Ranking-Ordnung und Ausfuehrungs-Hints.

    Ensemble-Reihenfolge aus `end_decision_binding` bleibt als Snapshot erhalten; Risiko- und
    Kontext-Treiber duerfen zulaessige Familien nach vorne ziehen.
    """
    raw_ranked = [
        _normalize_family(str(x).strip())
        for x in (end_decision_binding.get("exit_families_ranked") or [])
        if isinstance(x, str) and str(x).strip()
    ]
    ranked_valid = [x for x in raw_ranked if x in _VALID_EXIT_FAMILIES]

    primary_raw = _normalize_family(str(end_decision_binding.get("exit_family_primary") or "").strip())
    primary_valid = primary_raw if primary_raw in _VALID_EXIT_FAMILIES else None

    drivers: list[str] = []
    prepend: list[str] = []

    news = _news_score(db_row)
    if news is not None and news >= 70.0:
        if "news_risk_flatten" in _VALID_EXIT_FAMILIES:
            prepend.append("news_risk_flatten")
        drivers.append("driver_news_score_ge_70")

    mfe = _coerce_float(db_row.get("expected_mfe_bps"))
    mae = _coerce_float(db_row.get("expected_mae_bps"))
    if mfe is not None and mae is not None and mae > 1e-9:
        ratio = mfe / mae
        if ratio >= 2.35:
            if "trend_follow_runner" in _VALID_EXIT_FAMILIES:
                prepend.append("trend_follow_runner")
            drivers.append("driver_mfe_mae_ratio_high")
        elif ratio <= 1.12:
            if "time_stop" in _VALID_EXIT_FAMILIES:
                prepend.append("time_stop")
            drivers.append("driver_mfe_mae_ratio_low")

    micro = _primary_microstructure(db_row)
    spread_bps = _coerce_float(micro.get("spread_bps"))
    if spread_bps is not None and spread_bps >= 10.0:
        if "liquidity_target" in _VALID_EXIT_FAMILIES:
            prepend.append("liquidity_target")
        drivers.append("driver_wide_spread_bps")

    depth_ratio = _coerce_float(micro.get("depth_to_bar_volume_ratio"))
    if depth_ratio is not None and depth_ratio < 0.12:
        if "liquidity_target" in _VALID_EXIT_FAMILIES and "liquidity_target" not in prepend:
            prepend.append("liquidity_target")
        drivers.append("driver_thin_depth_ratio")

    market_family = str(db_row.get("market_family") or "").strip().lower()
    if market_family == "futures":
        fcw = abs(_coerce_float(micro.get("funding_cost_bps_window")) or 0.0)
        mis = abs(_coerce_float(micro.get("mark_index_spread_bps")) or 0.0)
        if fcw > 1.2 or mis > 15.0:
            if "basis_funding_unwind" in _VALID_EXIT_FAMILIES:
                prepend.append("basis_funding_unwind")
            drivers.append("driver_funding_or_basis_stress")

    playbook_family = str(db_row.get("playbook_family") or "").strip().lower()
    if playbook_family == "mean_reversion":
        if "mean_reversion_snapback" in _VALID_EXIT_FAMILIES:
            prepend.append("mean_reversion_snapback")
        drivers.append("driver_playbook_mean_reversion")

    merged: list[str] = []
    for x in prepend:
        if x in _VALID_EXIT_FAMILIES and x not in merged:
            merged.append(x)
    for x in ranked_valid:
        if x not in merged:
            merged.append(x)
    if primary_valid and primary_valid not in merged:
        merged.append(primary_valid)

    if not merged:
        merged = ["scale_out", "time_stop", "runner"]
        drivers.append("driver_fallback_default_ranking")

    effective_primary = merged[0]
    profile = _take_pct_profile_from_ranked(merged)
    hints = _execution_hints(ranked=merged, drivers=drivers, take_pct_profile=profile)

    return {
        "version": EXIT_FAMILY_RESOLUTION_VERSION,
        "primary": effective_primary,
        "ranked": merged[:12],
        "drivers": sorted(set(drivers)),
        "execution_hints": hints,
        "ensemble_exit_family_primary": end_decision_binding.get("exit_family_primary"),
        "ensemble_exit_families_ranked": list(end_decision_binding.get("exit_families_ranked") or []),
    }


def extract_exit_execution_hints_from_trace(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(trace, dict):
        return None
    h = trace.get("exit_execution_hints")
    if isinstance(h, dict):
        return h
    dcf = trace.get("decision_control_flow")
    if isinstance(dcf, dict):
        edb = dcf.get("end_decision_binding")
        if isinstance(edb, dict):
            h2 = edb.get("exit_execution_hints")
            if isinstance(h2, dict):
                return h2
        efr = dcf.get("exit_family_resolution")
        if isinstance(efr, dict):
            h3 = efr.get("execution_hints")
            if isinstance(h3, dict):
                return h3
    efr2 = trace.get("exit_family_resolution")
    if isinstance(efr2, dict):
        h4 = efr2.get("execution_hints")
        if isinstance(h4, dict):
            return h4
    return None


def extract_exit_family_resolution_from_trace(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(trace, dict):
        return None
    raw = trace.get("exit_family_resolution")
    if isinstance(raw, dict):
        return raw
    dcf = trace.get("decision_control_flow")
    if isinstance(dcf, dict):
        efr = dcf.get("exit_family_resolution")
        if isinstance(efr, dict):
            return efr
    return None
