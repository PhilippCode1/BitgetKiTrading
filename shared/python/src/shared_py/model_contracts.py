"""
Gemeinsame Modellvertraege fuer Feature-Snapshots, Signal-Outputs und Targets.

Diese Helpers kapseln:
- kanonische Timeframes
- stabile Schema-Hashes
- normalisierte Feature-/Output-Snapshots
- Contract-Metadaten fuer Training und Inferenz
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from shared_py.playbook_registry import (
    PLAYBOOK_DECISION_MODE_VALUES,
    PLAYBOOK_FAMILY_SET,
    PLAYBOOK_REGISTRY_VERSION,
    playbook_registry_descriptor,
)
from shared_py.regime_policy import (
    REGIME_ONTOLOGY_VERSION,
    REGIME_ROUTING_POLICY_VERSION,
    REGIME_STATE_VALUES,
    REGIME_TRANSITION_STATE_VALUES,
    regime_policy_descriptor,
)

MODEL_CONTRACT_VERSION = "2.1"

MODEL_TIMEFRAMES = ("1m", "5m", "15m", "1H", "4H")
_TIMEFRAME_ALIASES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1H",
    "1H": "1H",
    "4h": "4H",
    "4H": "4H",
}

MARKET_REGIME_VALUES = ("trend", "chop", "compression", "breakout", "shock", "dislocation")
REGIME_BIAS_VALUES = ("long", "short", "neutral")
_MARKET_REGIME_ALIASES = {
    "trend": "trend",
    "trending": "trend",
    "up": "trend",
    "down": "trend",
    "chop": "chop",
    "range": "chop",
    "compression": "compression",
    "compressed": "compression",
    "breakout": "breakout",
    "shock": "shock",
    "dislocation": "dislocation",
    "liquidity_stress": "dislocation",
    "microstructure_stress": "dislocation",
}
_REGIME_BIAS_ALIASES = {
    "long": "long",
    "up": "long",
    "bullish": "long",
    "short": "short",
    "down": "short",
    "bearish": "short",
    "neutral": "neutral",
    "range": "neutral",
    "flat": "neutral",
}

FEATURE_SCHEMA_VERSION = "3.0"
_META_MODEL_CALIBRATION_VALUES = ("sigmoid", "isotonic")
FEATURE_CONTRACT_META_FIELDS = ("feature_schema_version", "feature_schema_hash")
FEATURE_VALUE_FIELDS = (
    "canonical_instrument_id",
    "market_family",
    "product_type",
    "margin_account_mode",
    "instrument_metadata_snapshot_id",
    "symbol",
    "timeframe",
    "start_ts_ms",
    "atr_14",
    "atrp_14",
    "rsi_14",
    "ret_1",
    "ret_5",
    "momentum_score",
    "impulse_body_ratio",
    "impulse_upper_wick_ratio",
    "impulse_lower_wick_ratio",
    "range_score",
    "trend_ema_fast",
    "trend_ema_slow",
    "trend_slope_proxy",
    "trend_dir",
    "confluence_score_0_100",
    "vol_z_50",
    "spread_bps",
    "bid_depth_usdt_top25",
    "ask_depth_usdt_top25",
    "orderbook_imbalance",
    "depth_balance_ratio",
    "depth_to_bar_volume_ratio",
    "impact_buy_bps_5000",
    "impact_sell_bps_5000",
    "impact_buy_bps_10000",
    "impact_sell_bps_10000",
    "execution_cost_bps",
    "volatility_cost_bps",
    "funding_rate",
    "funding_rate_bps",
    "funding_cost_bps_window",
    "funding_time_to_next_ms",
    "open_interest",
    "open_interest_change_pct",
    "mark_index_spread_bps",
    "basis_bps",
    "session_drift_bps",
    "spread_persistence_bps",
    "mean_reversion_pressure_0_100",
    "breakout_compression_score_0_100",
    "realized_vol_cluster_0_100",
    "liquidation_distance_bps_max_leverage",
    "data_completeness_0_1",
    "staleness_score_0_1",
    "gap_count_lookback",
    "event_distance_ms",
    "feature_quality_status",
    "orderbook_age_ms",
    "funding_age_ms",
    "open_interest_age_ms",
    "liquidity_source",
    "funding_source",
    "open_interest_source",
    "source_event_id",
    "computed_ts_ms",
)
FEATURE_SNAPSHOT_FIELDS = FEATURE_CONTRACT_META_FIELDS + FEATURE_VALUE_FIELDS
FEATURE_FIELD_CATALOG_VERSION = "1.0"
FEATURE_FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "identity": (
        "canonical_instrument_id",
        "market_family",
        "product_type",
        "margin_account_mode",
        "instrument_metadata_snapshot_id",
        "symbol",
        "timeframe",
        "start_ts_ms",
        "source_event_id",
        "computed_ts_ms",
    ),
    "core": (
        "atr_14",
        "atrp_14",
        "rsi_14",
        "ret_1",
        "ret_5",
        "momentum_score",
        "impulse_body_ratio",
        "impulse_upper_wick_ratio",
        "impulse_lower_wick_ratio",
        "range_score",
        "trend_ema_fast",
        "trend_ema_slow",
        "trend_slope_proxy",
        "trend_dir",
        "confluence_score_0_100",
        "vol_z_50",
        "session_drift_bps",
        "breakout_compression_score_0_100",
        "realized_vol_cluster_0_100",
    ),
    "microstructure": (
        "spread_bps",
        "bid_depth_usdt_top25",
        "ask_depth_usdt_top25",
        "orderbook_imbalance",
        "depth_balance_ratio",
        "depth_to_bar_volume_ratio",
        "impact_buy_bps_5000",
        "impact_sell_bps_5000",
        "impact_buy_bps_10000",
        "impact_sell_bps_10000",
        "execution_cost_bps",
        "volatility_cost_bps",
        "spread_persistence_bps",
        "mean_reversion_pressure_0_100",
    ),
    "family": (
        "funding_rate",
        "funding_rate_bps",
        "funding_cost_bps_window",
        "funding_time_to_next_ms",
        "open_interest",
        "open_interest_change_pct",
        "mark_index_spread_bps",
        "basis_bps",
        "liquidation_distance_bps_max_leverage",
        "event_distance_ms",
    ),
    "quality": (
        "data_completeness_0_1",
        "staleness_score_0_1",
        "gap_count_lookback",
        "feature_quality_status",
        "orderbook_age_ms",
        "funding_age_ms",
        "open_interest_age_ms",
        "liquidity_source",
        "funding_source",
        "open_interest_source",
    ),
}
FEATURE_FIELD_FAMILY_SCOPE: dict[str, tuple[str, ...]] = {
    "funding_rate": ("futures",),
    "funding_rate_bps": ("futures",),
    "funding_cost_bps_window": ("futures",),
    "funding_time_to_next_ms": ("futures",),
    "open_interest": ("futures",),
    "open_interest_change_pct": ("futures",),
    "mark_index_spread_bps": ("futures",),
    "basis_bps": ("futures",),
    "liquidation_distance_bps_max_leverage": ("futures",),
}
FEATURE_GROUP_SPECIALIST_SCOPE: dict[str, tuple[str, ...]] = {
    "identity": ("family_specialists", "router", "meta"),
    "core": ("family_specialists", "regime_specialists", "router", "meta"),
    "microstructure": ("microstructure_specialists", "execution_risk", "router"),
    "family": ("family_specialists", "risk", "router"),
    "quality": ("quality_gates", "router", "learning"),
}

MODEL_OUTPUT_SCHEMA_VERSION = "9.0"
MODEL_OUTPUT_META_FIELDS = ("model_output_schema_version", "model_output_schema_hash")
MODEL_OUTPUT_FIELDS = (
    "signal_id",
    "symbol",
    "timeframe",
    "analysis_ts_ms",
    "market_regime",
    "regime_bias",
    "regime_confidence_0_1",
    "regime_reasons_json",
    "regime_state",
    "regime_substate",
    "regime_transition_state",
    "regime_transition_reasons_json",
    "regime_persistence_bars",
    "regime_policy_version",
    "direction",
    "signal_strength_0_100",
    "probability_0_1",
    "take_trade_prob",
    "take_trade_model_version",
    "take_trade_model_run_id",
    "take_trade_calibration_method",
    "expected_return_bps",
    "expected_mae_bps",
    "expected_mfe_bps",
    "target_projection_models_json",
    "model_uncertainty_0_1",
    "shadow_divergence_0_1",
    "model_ood_score_0_1",
    "model_ood_alert",
    "uncertainty_reasons_json",
    "ood_reasons_json",
    "abstention_reasons_json",
    "trade_action",
    "meta_trade_lane",
    "decision_confidence_0_1",
    "decision_policy_version",
    "allowed_leverage",
    "recommended_leverage",
    "leverage_policy_version",
    "leverage_cap_reasons_json",
    "signal_class",
    "structure_score_0_100",
    "momentum_score_0_100",
    "multi_timeframe_score_0_100",
    "news_score_0_100",
    "risk_score_0_100",
    "history_score_0_100",
    "weighted_composite_score_0_100",
    "rejection_state",
    "rejection_reasons_json",
    "decision_state",
    "reasons_json",
    "reward_risk_ratio",
    "expected_volatility_band",
    "scoring_model_version",
    "strategy_name",
    "playbook_id",
    "playbook_family",
    "playbook_decision_mode",
    "playbook_registry_version",
)
MODEL_OUTPUT_SNAPSHOT_FIELDS = MODEL_OUTPUT_META_FIELDS + MODEL_OUTPUT_FIELDS

MODEL_TARGET_SCHEMA_VERSION = "2.0"
MODEL_TARGET_FIELDS = (
    "decision_ts_ms",
    "take_trade_label",
    "expected_return_bps",
    "expected_return_gross_bps",
    "expected_mae_bps",
    "expected_mfe_bps",
    "liquidation_proximity_bps",
    "liquidation_risk",
    "direction_correct",
    "pnl_net_usdt",
    "stop_hit",
    "tp1_hit",
    "tp2_hit",
    "tp3_hit",
    "time_to_tp1_ms",
    "time_to_stop_ms",
    "stop_quality_score",
    "stop_distance_atr_mult",
    "slippage_bps_entry",
    "slippage_bps_exit",
    "market_regime",
    "error_labels_json",
)

_FEATURE_SCHEMA_MANIFEST = {
    "contract_version": MODEL_CONTRACT_VERSION,
    "schema_kind": "model_feature_snapshot",
    "schema_version": FEATURE_SCHEMA_VERSION,
    "fields": list(FEATURE_SNAPSHOT_FIELDS),
}
FEATURE_SCHEMA_HASH = hashlib.sha256(
    json.dumps(_FEATURE_SCHEMA_MANIFEST, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()
FEATURE_FIELD_CATALOG_HASH = hashlib.sha256(
    json.dumps(
        {
            "catalog_version": FEATURE_FIELD_CATALOG_VERSION,
            "groups": [
                {
                    "name": name,
                    "fields": list(fields),
                    "specialists": list(FEATURE_GROUP_SPECIALIST_SCOPE.get(name, ())),
                }
                for name, fields in FEATURE_FIELD_GROUPS.items()
            ],
            "family_scope": [
                {"field": name, "families": list(families)}
                for name, families in sorted(FEATURE_FIELD_FAMILY_SCOPE.items())
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()

_MODEL_OUTPUT_SCHEMA_MANIFEST = {
    "contract_version": MODEL_CONTRACT_VERSION,
    "schema_kind": "signal_model_output",
    "schema_version": MODEL_OUTPUT_SCHEMA_VERSION,
    "fields": list(MODEL_OUTPUT_SNAPSHOT_FIELDS),
}
MODEL_OUTPUT_SCHEMA_HASH = hashlib.sha256(
    json.dumps(_MODEL_OUTPUT_SCHEMA_MANIFEST, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
).hexdigest()

_MODEL_TARGET_SCHEMA_MANIFEST = {
    "contract_version": MODEL_CONTRACT_VERSION,
    "schema_kind": "learning_target",
    "schema_version": MODEL_TARGET_SCHEMA_VERSION,
    "fields": list(MODEL_TARGET_FIELDS),
}
MODEL_TARGET_SCHEMA_HASH = hashlib.sha256(
    json.dumps(_MODEL_TARGET_SCHEMA_MANIFEST, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
).hexdigest()

_FEATURE_REQUIRED_FIELDS = (
    "symbol",
    "timeframe",
    "start_ts_ms",
    "trend_dir",
    "source_event_id",
    "computed_ts_ms",
)
_FEATURE_NONNEGATIVE_FIELDS = (
    "atr_14",
    "atrp_14",
    "trend_ema_fast",
    "trend_ema_slow",
    "spread_bps",
    "bid_depth_usdt_top25",
    "ask_depth_usdt_top25",
    "depth_to_bar_volume_ratio",
    "impact_buy_bps_5000",
    "impact_sell_bps_5000",
    "impact_buy_bps_10000",
    "impact_sell_bps_10000",
    "execution_cost_bps",
    "volatility_cost_bps",
    "funding_rate_bps",
    "funding_cost_bps_window",
    "funding_time_to_next_ms",
    "open_interest",
    "spread_persistence_bps",
    "liquidation_distance_bps_max_leverage",
    "data_completeness_0_1",
    "staleness_score_0_1",
    "orderbook_age_ms",
    "funding_age_ms",
    "open_interest_age_ms",
)
_FEATURE_RATIO_FIELDS = (
    "impulse_body_ratio",
    "impulse_upper_wick_ratio",
    "impulse_lower_wick_ratio",
    "depth_balance_ratio",
)
_FEATURE_SCORE_FIELDS = ("range_score", "confluence_score_0_100", "rsi_14")
_FEATURE_OPTIONAL_FLOAT_FIELDS = (
    "atr_14",
    "atrp_14",
    "rsi_14",
    "ret_1",
    "ret_5",
    "momentum_score",
    "impulse_body_ratio",
    "impulse_upper_wick_ratio",
    "impulse_lower_wick_ratio",
    "range_score",
    "trend_ema_fast",
    "trend_ema_slow",
    "trend_slope_proxy",
    "confluence_score_0_100",
    "vol_z_50",
    "spread_bps",
    "bid_depth_usdt_top25",
    "ask_depth_usdt_top25",
    "orderbook_imbalance",
    "depth_balance_ratio",
    "depth_to_bar_volume_ratio",
    "impact_buy_bps_5000",
    "impact_sell_bps_5000",
    "impact_buy_bps_10000",
    "impact_sell_bps_10000",
    "execution_cost_bps",
    "volatility_cost_bps",
    "funding_rate",
    "funding_rate_bps",
    "funding_cost_bps_window",
    "open_interest",
    "open_interest_change_pct",
    "mark_index_spread_bps",
    "basis_bps",
    "session_drift_bps",
    "spread_persistence_bps",
    "mean_reversion_pressure_0_100",
    "breakout_compression_score_0_100",
    "realized_vol_cluster_0_100",
    "liquidation_distance_bps_max_leverage",
    "data_completeness_0_1",
    "staleness_score_0_1",
    "orderbook_age_ms",
    "funding_age_ms",
    "open_interest_age_ms",
)
_FEATURE_OPTIONAL_STR_FIELDS = (
    "product_type",
    "margin_account_mode",
    "instrument_metadata_snapshot_id",
    "feature_quality_status",
    "liquidity_source",
    "funding_source",
    "open_interest_source",
)
_FEATURE_OPTIONAL_INT_FIELDS = (
    "funding_time_to_next_ms",
    "gap_count_lookback",
    "event_distance_ms",
)

_MODEL_OUTPUT_REQUIRED_FIELDS = (
    "signal_id",
    "symbol",
    "timeframe",
    "analysis_ts_ms",
    "market_regime",
    "regime_bias",
    "regime_confidence_0_1",
    "regime_reasons_json",
    "direction",
    "signal_strength_0_100",
    "probability_0_1",
    "signal_class",
    "structure_score_0_100",
    "momentum_score_0_100",
    "multi_timeframe_score_0_100",
    "news_score_0_100",
    "risk_score_0_100",
    "history_score_0_100",
    "weighted_composite_score_0_100",
    "rejection_state",
    "rejection_reasons_json",
    "decision_state",
    "reasons_json",
    "scoring_model_version",
)
_MODEL_OUTPUT_SCORE_FIELDS = (
    "signal_strength_0_100",
    "structure_score_0_100",
    "momentum_score_0_100",
    "multi_timeframe_score_0_100",
    "news_score_0_100",
    "risk_score_0_100",
    "history_score_0_100",
    "weighted_composite_score_0_100",
)


def stable_json_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_model_timeframe(timeframe: str) -> str:
    raw = str(timeframe or "").strip()
    if not raw:
        return raw
    return _TIMEFRAME_ALIASES.get(raw, raw)


def normalize_market_regime(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None
    return _MARKET_REGIME_ALIASES.get(raw, raw)


def normalize_regime_bias(value: Any, *, fallback: Any | None = None) -> str | None:
    for candidate in (value, fallback):
        if candidate is None:
            continue
        raw = str(candidate).strip().lower()
        if not raw:
            continue
        normalized = _REGIME_BIAS_ALIASES.get(raw)
        if normalized is not None:
            return normalized
    return None


def build_feature_field_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for group_name, fields in FEATURE_FIELD_GROUPS.items():
        for field in fields:
            entry = catalog.setdefault(field, {"groups": [], "families": ["spot", "margin", "futures"]})
            entry["groups"].append(group_name)
            if field in FEATURE_FIELD_FAMILY_SCOPE:
                entry["families"] = list(FEATURE_FIELD_FAMILY_SCOPE[field])
    return catalog


def feature_contract_descriptor() -> dict[str, Any]:
    return {
        "contract_version": MODEL_CONTRACT_VERSION,
        "schema_kind": "model_feature_snapshot",
        "schema_version": FEATURE_SCHEMA_VERSION,
        "schema_hash": FEATURE_SCHEMA_HASH,
        "fields": list(FEATURE_SNAPSHOT_FIELDS),
        "timeframes": list(MODEL_TIMEFRAMES),
        "field_catalog_version": FEATURE_FIELD_CATALOG_VERSION,
        "field_catalog_hash": FEATURE_FIELD_CATALOG_HASH,
        "field_groups": {
            name: {
                "fields": list(fields),
                "specialists": list(FEATURE_GROUP_SPECIALIST_SCOPE.get(name, ())),
            }
            for name, fields in FEATURE_FIELD_GROUPS.items()
        },
        "field_catalog": build_feature_field_catalog(),
    }


def model_output_contract_descriptor() -> dict[str, Any]:
    return {
        "contract_version": MODEL_CONTRACT_VERSION,
        "schema_kind": "signal_model_output",
        "schema_version": MODEL_OUTPUT_SCHEMA_VERSION,
        "schema_hash": MODEL_OUTPUT_SCHEMA_HASH,
        "fields": list(MODEL_OUTPUT_SNAPSHOT_FIELDS),
        "playbook_registry_version": PLAYBOOK_REGISTRY_VERSION,
        "regime_ontology_version": REGIME_ONTOLOGY_VERSION,
        "regime_policy_version": REGIME_ROUTING_POLICY_VERSION,
    }


def model_target_contract_descriptor() -> dict[str, Any]:
    return {
        "contract_version": MODEL_CONTRACT_VERSION,
        "schema_kind": "learning_target",
        "schema_version": MODEL_TARGET_SCHEMA_VERSION,
        "schema_hash": MODEL_TARGET_SCHEMA_HASH,
        "fields": list(MODEL_TARGET_FIELDS),
    }


def build_quality_gate(issues: Sequence[str] | None = None) -> dict[str, Any]:
    normalized = sorted({str(item).strip() for item in issues or [] if str(item).strip()})
    return {"passed": not normalized, "issues": normalized}


def build_model_contract_bundle(
    *,
    quality_issues: Sequence[str] | None = None,
    active_models: Sequence[Mapping[str, Any]] | None = None,
    target_labeling_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "contract_version": MODEL_CONTRACT_VERSION,
        "feature_snapshot": feature_contract_descriptor(),
        "model_output": model_output_contract_descriptor(),
        "targets": model_target_contract_descriptor(),
        "playbook_registry": playbook_registry_descriptor(),
        "regime_policy": regime_policy_descriptor(),
        "quality_gate": build_quality_gate(quality_issues),
        "active_models": _normalize_active_models(active_models),
    }
    if target_labeling_audit:
        out["target_labeling"] = dict(target_labeling_audit)
    return out


def normalize_feature_row(row: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    if row is None:
        return None, ["missing_feature_row"]

    raw = dict(row)
    issues: list[str] = []
    out: dict[str, Any] = {
        "feature_schema_version": str(raw.get("feature_schema_version") or FEATURE_SCHEMA_VERSION),
        "feature_schema_hash": str(raw.get("feature_schema_hash") or FEATURE_SCHEMA_HASH),
    }

    if out["feature_schema_version"] != FEATURE_SCHEMA_VERSION:
        issues.append("feature_schema_version_mismatch")
    if out["feature_schema_hash"] != FEATURE_SCHEMA_HASH:
        issues.append("feature_schema_hash_mismatch")

    symbol = str(raw.get("symbol") or "").strip().upper()
    out["symbol"] = symbol
    if not symbol:
        issues.append("feature_symbol_missing")

    canonical_instrument_id = str(raw.get("canonical_instrument_id") or "").strip()
    out["canonical_instrument_id"] = (
        canonical_instrument_id or f"bitget:unknown:unknown:{symbol or 'UNKNOWN'}"
    )

    market_family = str(raw.get("market_family") or "unknown").strip().lower()
    out["market_family"] = market_family
    if market_family not in {"spot", "margin", "futures", "unknown"}:
        issues.append("feature_market_family_invalid")

    timeframe = normalize_model_timeframe(str(raw.get("timeframe") or "").strip())
    out["timeframe"] = timeframe
    if timeframe not in MODEL_TIMEFRAMES:
        issues.append("feature_timeframe_invalid")

    out["start_ts_ms"] = _coerce_positive_int(raw.get("start_ts_ms"), "feature_start_ts_invalid", issues)
    out["computed_ts_ms"] = _coerce_positive_int(
        raw.get("computed_ts_ms"),
        "feature_computed_ts_invalid",
        issues,
    )

    source_event_id = str(raw.get("source_event_id") or "").strip()
    out["source_event_id"] = source_event_id
    if not source_event_id:
        issues.append("feature_source_event_missing")

    trend_dir = _coerce_int(raw.get("trend_dir"), "feature_trend_dir_invalid", issues)
    if trend_dir not in (-1, 0, 1):
        issues.append("feature_trend_dir_invalid")
    out["trend_dir"] = trend_dir

    for field in _FEATURE_OPTIONAL_FLOAT_FIELDS:
        value = _coerce_float(raw.get(field), field, issues)
        out[field] = value
    for field in _FEATURE_OPTIONAL_INT_FIELDS:
        out[field] = _coerce_int(raw.get(field), f"{field}_invalid", issues)
    for field in _FEATURE_OPTIONAL_STR_FIELDS:
        out[field] = _coerce_str(raw.get(field))

    if out["atr_14"] is not None and out["atr_14"] < 0:
        issues.append("feature_atr_negative")
    if out["atrp_14"] is not None and out["atrp_14"] < 0:
        issues.append("feature_atrp_negative")
    if out["trend_ema_fast"] is not None and out["trend_ema_fast"] <= 0:
        issues.append("feature_trend_ema_fast_invalid")
    if out["trend_ema_slow"] is not None and out["trend_ema_slow"] <= 0:
        issues.append("feature_trend_ema_slow_invalid")
    if out["rsi_14"] is not None and not 0 <= out["rsi_14"] <= 100:
        issues.append("feature_rsi_out_of_range")
    if out["momentum_score"] is not None and not -100 <= out["momentum_score"] <= 100:
        issues.append("feature_momentum_out_of_range")
    for field in _FEATURE_RATIO_FIELDS:
        value = out.get(field)
        if value is not None and not 0 <= value <= 1:
            issues.append(f"{field}_out_of_range")
    if out["orderbook_imbalance"] is not None and not -1 <= out["orderbook_imbalance"] <= 1:
        issues.append("orderbook_imbalance_out_of_range")
    for field in (
        "range_score",
        "confluence_score_0_100",
        "mean_reversion_pressure_0_100",
        "breakout_compression_score_0_100",
        "realized_vol_cluster_0_100",
    ):
        value = out.get(field)
        if value is not None and not 0 <= value <= 100:
            issues.append(f"{field}_out_of_range")
    for field in ("data_completeness_0_1", "staleness_score_0_1"):
        value = out.get(field)
        if value is not None and not 0 <= value <= 1:
            issues.append(f"{field}_out_of_range")
    for field in _FEATURE_NONNEGATIVE_FIELDS:
        value = out.get(field)
        if value is not None and value < 0:
            issues.append(f"{field}_negative")
    if out["funding_rate"] is not None and not -1 <= out["funding_rate"] <= 1:
        issues.append("funding_rate_out_of_range")
    if out["open_interest_change_pct"] is not None and out["open_interest_change_pct"] < -100:
        issues.append("open_interest_change_pct_out_of_range")
    for field in ("funding_time_to_next_ms", "gap_count_lookback", "event_distance_ms"):
        value = out.get(field)
        if value is not None and value < 0:
            issues.append(f"{field}_negative")
    if (
        out["feature_quality_status"] is not None
        and out["feature_quality_status"] not in {"ok", "degraded", "invalid"}
    ):
        issues.append("feature_quality_status_invalid")
    if market_family not in {"futures", "unknown"}:
        for field in (
            "funding_rate",
            "funding_rate_bps",
            "funding_cost_bps_window",
            "funding_time_to_next_ms",
            "open_interest",
            "open_interest_change_pct",
            "mark_index_spread_bps",
            "basis_bps",
            "liquidation_distance_bps_max_leverage",
        ):
            if out.get(field) is not None:
                issues.append(f"{field}_not_applicable_for_family")
        if out["funding_source"] not in {None, "missing", "not_applicable"}:
            issues.append("funding_source_not_applicable_for_family")
        if out["open_interest_source"] not in {None, "missing", "not_applicable"}:
            issues.append("open_interest_source_not_applicable_for_family")

    return out, sorted(set(issues))


def build_feature_snapshot(
    *,
    primary_timeframe: str,
    primary_feature: Mapping[str, Any] | None,
    features_by_tf: Mapping[str, Mapping[str, Any] | None],
    quality_issues: Sequence[str] | None = None,
) -> dict[str, Any]:
    primary_tf = normalize_model_timeframe(primary_timeframe)
    combined_rows: dict[str, Mapping[str, Any] | None] = {
        normalize_model_timeframe(tf): row for tf, row in features_by_tf.items()
    }
    if primary_feature is not None:
        combined_rows[primary_tf] = primary_feature

    normalized_rows: dict[str, dict[str, Any] | None] = {}
    issues: list[str] = list(quality_issues or [])
    for tf in MODEL_TIMEFRAMES:
        normalized, row_issues = normalize_feature_row(combined_rows.get(tf))
        normalized_rows[tf] = normalized
        issues.extend(f"{tf}:{item}" for item in row_issues if item != "missing_feature_row")
        if normalized is None:
            issues.append(f"missing_feature_tf_{tf}")

    snapshot = {
        "contract_version": MODEL_CONTRACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "feature_field_catalog_version": FEATURE_FIELD_CATALOG_VERSION,
        "feature_field_catalog_hash": FEATURE_FIELD_CATALOG_HASH,
        "primary_timeframe": primary_tf,
        "primary_tf": normalized_rows.get(primary_tf),
        "timeframes": normalized_rows,
        "quality_gate": build_quality_gate(issues),
    }
    if snapshot["primary_tf"] is None:
        snapshot["missing"] = True
    return snapshot


def normalize_model_output_row(
    row: Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if row is None:
        return None, ["missing_model_output_row"]

    raw = dict(row)
    issues: list[str] = []
    out: dict[str, Any] = {
        "model_output_schema_version": str(
            raw.get("model_output_schema_version") or MODEL_OUTPUT_SCHEMA_VERSION
        ),
        "model_output_schema_hash": str(raw.get("model_output_schema_hash") or MODEL_OUTPUT_SCHEMA_HASH),
    }

    if out["model_output_schema_version"] != MODEL_OUTPUT_SCHEMA_VERSION:
        issues.append("model_output_schema_version_mismatch")
    if out["model_output_schema_hash"] != MODEL_OUTPUT_SCHEMA_HASH:
        issues.append("model_output_schema_hash_mismatch")

    for field in (
        "signal_id",
        "symbol",
        "direction",
        "signal_class",
        "decision_state",
        "take_trade_model_version",
        "take_trade_model_run_id",
        "take_trade_calibration_method",
    ):
        value = raw.get(field)
        out[field] = str(value).strip() if value is not None else None
    out["market_regime"] = normalize_market_regime(raw.get("market_regime"))
    out["regime_bias"] = normalize_regime_bias(
        raw.get("regime_bias"),
        fallback=raw.get("market_regime"),
    )
    if out["take_trade_calibration_method"] is not None:
        out["take_trade_calibration_method"] = out["take_trade_calibration_method"].lower()

    out["timeframe"] = normalize_model_timeframe(str(raw.get("timeframe") or "").strip())
    out["analysis_ts_ms"] = _coerce_positive_int(raw.get("analysis_ts_ms"), "analysis_ts_invalid", issues)
    out["rejection_state"] = bool(raw.get("rejection_state"))
    out["model_ood_alert"] = bool(raw.get("model_ood_alert"))
    out["rejection_reasons_json"] = _as_list(raw.get("rejection_reasons_json"))
    out["regime_reasons_json"] = _as_list(raw.get("regime_reasons_json"))
    out["regime_transition_reasons_json"] = _as_list(raw.get("regime_transition_reasons_json"))
    out["target_projection_models_json"] = _as_list(raw.get("target_projection_models_json"))
    out["uncertainty_reasons_json"] = _as_list(raw.get("uncertainty_reasons_json"))
    out["ood_reasons_json"] = _as_list(raw.get("ood_reasons_json"))
    out["abstention_reasons_json"] = _as_list(raw.get("abstention_reasons_json"))
    out["reasons_json"] = _as_dict(raw.get("reasons_json"))
    out["scoring_model_version"] = str(raw.get("scoring_model_version") or "").strip() or None
    out["decision_policy_version"] = str(raw.get("decision_policy_version") or "").strip() or None
    out["leverage_policy_version"] = str(raw.get("leverage_policy_version") or "").strip() or None
    out["leverage_cap_reasons_json"] = _as_list(raw.get("leverage_cap_reasons_json"))
    out["strategy_name"] = str(raw.get("strategy_name") or "").strip() or None
    out["playbook_id"] = str(raw.get("playbook_id") or "").strip() or None
    out["playbook_family"] = str(raw.get("playbook_family") or "").strip() or None
    out["playbook_registry_version"] = (
        str(raw.get("playbook_registry_version") or "").strip() or None
    )
    out["playbook_decision_mode"] = (
        str(raw.get("playbook_decision_mode") or "").strip().lower()
        or ("selected" if out["playbook_id"] else "playbookless")
    )
    out["trade_action"] = str(raw.get("trade_action") or "").strip().lower() or None
    out["meta_trade_lane"] = str(raw.get("meta_trade_lane") or "").strip().lower() or None
    out["regime_state"] = (
        str(raw.get("regime_state") or "").strip().lower() or out["market_regime"]
    )
    out["regime_substate"] = (
        str(raw.get("regime_substate") or "").strip().lower()
        or (f"{out['regime_state']}_default" if out["regime_state"] else None)
    )
    out["regime_transition_state"] = (
        str(raw.get("regime_transition_state") or "").strip().lower() or "stable"
    )
    out["regime_policy_version"] = (
        str(raw.get("regime_policy_version") or "").strip() or REGIME_ROUTING_POLICY_VERSION
    )
    regime_persistence_bars = raw.get("regime_persistence_bars")
    if regime_persistence_bars in (None, ""):
        out["regime_persistence_bars"] = 1
    else:
        try:
            out["regime_persistence_bars"] = int(regime_persistence_bars)
        except (TypeError, ValueError):
            out["regime_persistence_bars"] = 1
            issues.append("regime_persistence_bars_invalid")

    for field in (
        "signal_strength_0_100",
        "probability_0_1",
        "take_trade_prob",
        "expected_return_bps",
        "expected_mae_bps",
        "expected_mfe_bps",
        "model_uncertainty_0_1",
        "shadow_divergence_0_1",
        "model_ood_score_0_1",
        "decision_confidence_0_1",
        "regime_confidence_0_1",
        "structure_score_0_100",
        "momentum_score_0_100",
        "multi_timeframe_score_0_100",
        "news_score_0_100",
        "risk_score_0_100",
        "history_score_0_100",
        "weighted_composite_score_0_100",
        "reward_risk_ratio",
        "expected_volatility_band",
    ):
        out[field] = _coerce_float(raw.get(field), field, issues)

    for field in _MODEL_OUTPUT_REQUIRED_FIELDS:
        value = out.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            issues.append(f"{field}_missing")

    if out["timeframe"] not in MODEL_TIMEFRAMES:
        issues.append("timeframe_invalid")
    if out["market_regime"] not in set(MARKET_REGIME_VALUES):
        issues.append("market_regime_invalid")
    if out["regime_state"] not in set(REGIME_STATE_VALUES):
        issues.append("regime_state_invalid")
    if out["regime_transition_state"] not in set(REGIME_TRANSITION_STATE_VALUES):
        issues.append("regime_transition_state_invalid")
    if out["regime_bias"] not in set(REGIME_BIAS_VALUES):
        issues.append("regime_bias_invalid")
    if out["direction"] not in {"long", "short", "neutral"}:
        issues.append("direction_invalid")
    if out["signal_class"] not in {"mikro", "kern", "gross", "warnung"}:
        issues.append("signal_class_invalid")
    if out["decision_state"] not in {"accepted", "downgraded", "rejected"}:
        issues.append("decision_state_invalid")
    if out["signal_strength_0_100"] is not None and not 0 <= out["signal_strength_0_100"] <= 100:
        issues.append("signal_strength_out_of_range")
    if out["probability_0_1"] is not None and not 0 <= out["probability_0_1"] <= 1:
        issues.append("probability_out_of_range")
    if out["take_trade_prob"] is not None and not 0 <= out["take_trade_prob"] <= 1:
        issues.append("take_trade_prob_out_of_range")
    if out["model_uncertainty_0_1"] is not None and not 0 <= out["model_uncertainty_0_1"] <= 1:
        issues.append("model_uncertainty_out_of_range")
    if out["shadow_divergence_0_1"] is not None and not 0 <= out["shadow_divergence_0_1"] <= 1:
        issues.append("shadow_divergence_out_of_range")
    if out["model_ood_score_0_1"] is not None and not 0 <= out["model_ood_score_0_1"] <= 1:
        issues.append("model_ood_score_out_of_range")
    if out["decision_confidence_0_1"] is not None and not 0 <= out["decision_confidence_0_1"] <= 1:
        issues.append("decision_confidence_out_of_range")
    if out["expected_mae_bps"] is not None and out["expected_mae_bps"] < 0:
        issues.append("expected_mae_bps_negative")
    if out["expected_mfe_bps"] is not None and out["expected_mfe_bps"] < 0:
        issues.append("expected_mfe_bps_negative")
    if out["regime_confidence_0_1"] is not None and not 0 <= out["regime_confidence_0_1"] <= 1:
        issues.append("regime_confidence_out_of_range")
    if (
        out["take_trade_calibration_method"] is not None
        and out["take_trade_calibration_method"] not in _META_MODEL_CALIBRATION_VALUES
    ):
        issues.append("take_trade_calibration_method_invalid")
    for field in _MODEL_OUTPUT_SCORE_FIELDS[1:]:
        value = out.get(field)
        if value is not None and not 0 <= value <= 100:
            issues.append(f"{field}_out_of_range")
    if out["expected_volatility_band"] is not None and out["expected_volatility_band"] < 0:
        issues.append("expected_volatility_band_negative")
    if out["reward_risk_ratio"] is not None and out["reward_risk_ratio"] < 0:
        issues.append("reward_risk_ratio_negative")
    if out["playbook_decision_mode"] not in set(PLAYBOOK_DECISION_MODE_VALUES):
        issues.append("playbook_decision_mode_invalid")
    if out["playbook_family"] is not None and out["playbook_family"] not in PLAYBOOK_FAMILY_SET:
        issues.append("playbook_family_invalid")
    if out["playbook_decision_mode"] == "selected":
        if out["playbook_id"] is None:
            issues.append("playbook_id_missing")
        if out["playbook_family"] is None:
            issues.append("playbook_family_missing")
        if out["playbook_registry_version"] is None:
            issues.append("playbook_registry_version_missing")
    if out["regime_persistence_bars"] < 1:
        issues.append("regime_persistence_bars_invalid")
    if out["trade_action"] is None:
        out["trade_action"] = "do_not_trade" if out["decision_state"] == "rejected" else "allow_trade"
    if out["trade_action"] not in {"allow_trade", "do_not_trade"}:
        issues.append("trade_action_invalid")
    if out["meta_trade_lane"] is not None:
        from shared_py.signal_contracts import META_TRADE_LANE_VALUES

        if out["meta_trade_lane"] not in set(META_TRADE_LANE_VALUES):
            issues.append("meta_trade_lane_invalid")
    allowed_leverage = raw.get("allowed_leverage")
    if allowed_leverage in (None, ""):
        out["allowed_leverage"] = None
    else:
        try:
            out["allowed_leverage"] = int(allowed_leverage)
        except (TypeError, ValueError):
            out["allowed_leverage"] = None
            issues.append("allowed_leverage_invalid")
    if out["allowed_leverage"] is not None and not 0 <= out["allowed_leverage"] <= 75:
        issues.append("allowed_leverage_out_of_range")
    recommended_leverage = raw.get("recommended_leverage")
    if recommended_leverage in (None, ""):
        out["recommended_leverage"] = None
    else:
        try:
            out["recommended_leverage"] = int(recommended_leverage)
        except (TypeError, ValueError):
            out["recommended_leverage"] = None
            issues.append("recommended_leverage_invalid")
    if out["recommended_leverage"] is not None and not 7 <= out["recommended_leverage"] <= 75:
        issues.append("recommended_leverage_out_of_range")

    return out, sorted(set(issues))


def build_model_output_snapshot(
    row: Mapping[str, Any] | None,
    *,
    quality_issues: Sequence[str] | None = None,
) -> dict[str, Any]:
    normalized, row_issues = normalize_model_output_row(row)
    issues = list(row_issues)
    issues.extend(list(quality_issues or []))
    if normalized is None:
        return {
            "contract_version": MODEL_CONTRACT_VERSION,
            "model_output_schema_version": MODEL_OUTPUT_SCHEMA_VERSION,
            "model_output_schema_hash": MODEL_OUTPUT_SCHEMA_HASH,
            "missing": True,
            "quality_gate": build_quality_gate(issues),
        }

    out: dict[str, Any] = {
        "contract_version": MODEL_CONTRACT_VERSION,
        **normalized,
        "quality_gate": build_quality_gate(issues),
    }
    rj = row.get("reasons_json")
    if isinstance(rj, dict):
        dcf = rj.get("decision_control_flow")
        if isinstance(dcf, dict):
            efr = dcf.get("exit_family_resolution")
            if isinstance(efr, dict):
                out["exit_family_resolution"] = efr
    return out


def extract_active_models_from_signal_row(row: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if row is None:
        return []
    models: list[dict[str, Any]] = []
    version = str(row.get("take_trade_model_version") or "").strip() or None
    run_id = str(row.get("take_trade_model_run_id") or "").strip() or None
    calibration_method = str(row.get("take_trade_calibration_method") or "").strip().lower() or None
    if not (version is None and run_id is None and calibration_method is None):
        models.append(
            {
                "model_name": "take_trade_prob",
                "version": version,
                "run_id": run_id,
                "output_field": "take_trade_prob",
                "target_field": "take_trade_label",
                "calibration_method": calibration_method,
            }
        )
    projection_models = _as_list(row.get("target_projection_models_json"))
    if not projection_models:
        source_snapshot = _as_dict(row.get("source_snapshot_json"))
        projection_models = _as_list(source_snapshot.get("target_projection_models"))
    models.extend(item for item in projection_models if isinstance(item, dict))
    return _normalize_active_models(models)


def extract_primary_feature_snapshot(raw: Any) -> dict[str, Any]:
    snapshot = _as_dict(raw)
    primary = snapshot.get("primary_tf")
    if isinstance(primary, dict):
        return primary
    timeframes = snapshot.get("timeframes")
    if isinstance(timeframes, dict):
        primary_timeframe = normalize_model_timeframe(str(snapshot.get("primary_timeframe") or ""))
        candidate = timeframes.get(primary_timeframe)
        if isinstance(candidate, dict):
            return candidate
    if any(field in snapshot for field in FEATURE_VALUE_FIELDS):
        return snapshot
    return {}


def _coerce_positive_int(value: Any, issue: str, issues: list[str]) -> int | None:
    coerced = _coerce_int(value, issue, issues)
    if coerced is None or coerced <= 0:
        issues.append(issue)
    return coerced


def _coerce_int(value: Any, issue: str, issues: list[str]) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        issues.append(issue)
        return None


def _coerce_float(value: Any, field: str, issues: list[str]) -> float | None:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        issues.append(f"{field}_invalid")
        return None
    if not math.isfinite(result):
        issues.append(f"{field}_invalid")
        return None
    return result


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return list(parsed) if isinstance(parsed, list) else []
    return []


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


def _normalize_active_models(active_models: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in active_models or []:
        model_name = str(item.get("model_name") or "").strip()
        if not model_name:
            continue
        normalized.append(
            {
                "model_name": model_name,
                "version": _coerce_str(item.get("version")),
                "run_id": _coerce_str(item.get("run_id")),
                "output_field": _coerce_str(item.get("output_field")),
                "target_field": _coerce_str(item.get("target_field")),
                "calibration_method": _coerce_str(item.get("calibration_method")),
                "scaling_method": _coerce_str(item.get("scaling_method")),
            }
        )
    return normalized
