"""
Shadow-vs-Live-Forensik: strukturierte Abweichungsmetriken (Prompt 30).

Ergebnis ist JSON-serialisierbar und kann in source_snapshot_json, Analytics-DB
oder Reports abgelegt werden.
"""

from __future__ import annotations

import json
from typing import Any

FORENSICS_SCHEMA_VERSION = "slf-p30-v1"


def _as_dict(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            o = json.loads(raw)
            return o if isinstance(o, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _max_feature_age_ms(feature_snapshot: dict[str, Any]) -> float | None:
    primary = feature_snapshot.get("primary_tf")
    ages: list[float] = []
    if isinstance(primary, dict):
        for key in ("orderbook_age_ms", "funding_age_ms", "open_interest_age_ms"):
            v = _f(primary.get(key))
            if v is not None:
                ages.append(v)
    tfs = feature_snapshot.get("timeframes")
    if isinstance(tfs, dict):
        for row in tfs.values():
            if not isinstance(row, dict):
                continue
            for key in ("orderbook_age_ms", "funding_age_ms", "open_interest_age_ms"):
                v = _f(row.get(key))
                if v is not None:
                    ages.append(v)
    if not ages:
        return None
    return max(ages)


def compute_shadow_live_divergence(
    live_row: dict[str, Any],
    shadow_row: dict[str, Any],
) -> dict[str, Any]:
    """
    Vergleicht zwei Signal-Zeilen (z. B. gleiche logische Entscheidung: Live-Champion vs Shadow).

    Blocker-Klassifikation: siehe docs/shadow_live_divergence.md
    """
    live_snap = _as_dict(live_row.get("source_snapshot_json"))
    sh_snap = _as_dict(shadow_row.get("source_snapshot_json"))
    live_fs = _as_dict(live_snap.get("feature_snapshot"))
    sh_fs = _as_dict(sh_snap.get("feature_snapshot"))

    age_l = _max_feature_age_ms(live_fs)
    age_s = _max_feature_age_ms(sh_fs)
    data_age_delta_ms: float | None = None
    if age_l is not None and age_s is not None:
        data_age_delta_ms = abs(age_l - age_s)

    reg_l = str(live_row.get("market_regime") or "").strip().lower()
    reg_s = str(shadow_row.get("market_regime") or "").strip().lower()
    regime_match = reg_l == reg_s if reg_l and reg_s else None

    ta_l = str(live_row.get("trade_action") or "").strip().lower()
    ta_s = str(shadow_row.get("trade_action") or "").strip().lower()
    trade_action_match = ta_l == ta_s if ta_l and ta_s else None

    lane_l = str(live_row.get("meta_trade_lane") or "").strip().lower()
    lane_s = str(shadow_row.get("meta_trade_lane") or "").strip().lower()
    meta_lane_match = lane_l == lane_s if lane_l and lane_s else None

    live_h = _as_dict(live_snap.get("hybrid_decision"))
    sh_h = _as_dict(sh_snap.get("hybrid_decision"))
    live_gov = _as_dict(live_h.get("risk_governor"))
    sh_gov = _as_dict(sh_h.get("risk_governor"))
    live_hard = list(live_gov.get("hard_block_reasons_json") or [])
    sh_hard = list(sh_gov.get("hard_block_reasons_json") or [])

    ttp_l = _f(live_row.get("take_trade_prob"))
    ttp_s = _f(shadow_row.get("take_trade_prob"))
    take_trade_prob_delta: float | None = None
    if ttp_l is not None and ttp_s is not None:
        take_trade_prob_delta = abs(ttp_l - ttp_s)

    exit_l = str(live_row.get("stop_trigger_type") or "").strip().lower()
    exit_s = str(shadow_row.get("stop_trigger_type") or "").strip().lower()
    exit_config_match = exit_l == exit_s if exit_l or exit_s else None

    blockers: list[str] = []
    if trade_action_match is False and ta_l == "allow_trade" and ta_s == "do_not_trade":
        blockers.append("shadow_blocks_trade_live_would_allow")
    if trade_action_match is False and ta_l == "do_not_trade" and ta_s == "allow_trade":
        blockers.append("live_blocks_trade_shadow_would_allow")
    if meta_lane_match is False:
        blockers.append("meta_trade_lane_mismatch")
    if sorted(live_hard) != sorted(sh_hard):
        blockers.append("risk_governor_hard_reasons_differ")
    if regime_match is False:
        blockers.append("market_regime_mismatch")

    warnings: list[str] = []
    if data_age_delta_ms is not None and data_age_delta_ms > 5_000:
        warnings.append("large_feature_age_delta_ms")
    if take_trade_prob_delta is not None and take_trade_prob_delta > 0.12:
        warnings.append("large_take_trade_prob_delta")

    return {
        "forensics_schema_version": FORENSICS_SCHEMA_VERSION,
        "data_age_delta_ms": data_age_delta_ms,
        "regime_match": regime_match,
        "regime_live": reg_l or None,
        "regime_shadow": reg_s or None,
        "trade_action_match": trade_action_match,
        "trade_action_live": ta_l or None,
        "trade_action_shadow": ta_s or None,
        "meta_lane_match": meta_lane_match,
        "meta_trade_lane_live": lane_l or None,
        "meta_trade_lane_shadow": lane_s or None,
        "risk_governor_hard_live": live_hard,
        "risk_governor_hard_shadow": sh_hard,
        "take_trade_prob_delta": take_trade_prob_delta,
        "exit_stop_trigger_match": exit_config_match,
        "blockers": blockers,
        "warnings": warnings,
        "correlation_live": live_snap.get("correlation_chain"),
        "correlation_shadow": sh_snap.get("correlation_chain"),
    }
