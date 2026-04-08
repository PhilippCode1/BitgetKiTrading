from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np

from shared_py.model_contracts import (
    MARKET_REGIME_VALUES,
    MODEL_TIMEFRAMES,
    REGIME_BIAS_VALUES,
    extract_primary_feature_snapshot,
    normalize_market_regime,
    normalize_model_timeframe,
    normalize_regime_bias,
    stable_json_hash,
)

TAKE_TRADE_MODEL_NAME = "take_trade_prob"
TAKE_TRADE_TARGET_FIELD = "take_trade_label"
TAKE_TRADE_MODEL_KIND = "hist_gradient_boosting_classifier"
TAKE_TRADE_CALIBRATION_METHODS = ("sigmoid", "isotonic")
BPS_REGRESSION_MODEL_KIND = "hist_gradient_boosting_regressor"
EXPECTED_RETURN_BPS_MODEL_NAME = "expected_return_bps"
EXPECTED_MAE_BPS_MODEL_NAME = "expected_mae_bps"
EXPECTED_MFE_BPS_MODEL_NAME = "expected_mfe_bps"
BPS_REGRESSION_MODEL_NAMES = (
    EXPECTED_RETURN_BPS_MODEL_NAME,
    EXPECTED_MAE_BPS_MODEL_NAME,
    EXPECTED_MFE_BPS_MODEL_NAME,
)

MARKET_REGIME_CLASSIFIER_MODEL_NAME = "market_regime_classifier"
MARKET_REGIME_TARGET_FIELD = "market_regime"
REGIME_CLASSIFIER_MODEL_KIND = "hist_gradient_boosting_classifier_multiclass"
REGIME_MODEL_FEATURE_SCHEMA_VERSION = "2.0"

_NUMERIC_FIELDS = (
    "signal_strength_0_100",
    "heuristic_probability_0_1",
    "structure_score_0_100",
    "momentum_score_layer_0_100",
    "multi_timeframe_score_0_100",
    "news_score_0_100",
    "risk_score_0_100",
    "history_score_0_100",
    "weighted_composite_score_0_100",
    "reward_risk_ratio",
    "expected_volatility_band",
    "regime_confidence_0_1",
    "atr_14",
    "atrp_14",
    "rsi_14",
    "ret_1",
    "ret_5",
    "momentum_score_feature",
    "impulse_body_ratio",
    "impulse_upper_wick_ratio",
    "impulse_lower_wick_ratio",
    "range_score",
    "trend_slope_proxy",
    "confluence_score_0_100",
    "vol_z_50",
    "spread_bps",
    "depth_balance_ratio",
    "depth_to_bar_volume_ratio",
    "impact_buy_bps_5000",
    "impact_sell_bps_5000",
    "execution_cost_bps",
    "volatility_cost_bps",
    "funding_rate_bps",
    "funding_cost_bps_window",
    "open_interest_change_pct",
    "trend_dir_primary",
    "trend_dir_1m",
    "trend_dir_5m",
    "trend_dir_15m",
    "trend_dir_1H",
    "trend_dir_4H",
    "high_tf_alignment_ratio",
)
_TIMEFRAME_ONE_HOT_FIELDS = tuple(f"timeframe_is_{tf}" for tf in MODEL_TIMEFRAMES)
_DIRECTION_ONE_HOT_FIELDS = ("direction_is_long", "direction_is_short", "direction_is_neutral")
_SIGNAL_CLASS_ONE_HOT_FIELDS = (
    "signal_class_is_mikro",
    "signal_class_is_kern",
    "signal_class_is_gross",
    "signal_class_is_warnung",
)
_DECISION_STATE_ONE_HOT_FIELDS = (
    "decision_state_is_accepted",
    "decision_state_is_downgraded",
    "decision_state_is_rejected",
)
_MARKET_REGIME_ONE_HOT_FIELDS = tuple(
    f"market_regime_is_{regime}" for regime in MARKET_REGIME_VALUES
)
_REGIME_BIAS_ONE_HOT_FIELDS = tuple(f"regime_bias_is_{bias}" for bias in REGIME_BIAS_VALUES)
_BINARY_FLAG_FIELDS = (
    "liquidity_source_orderbook_levels",
    "liquidity_source_fallback",
    "funding_source_present",
    "open_interest_source_present",
)

SIGNAL_MODEL_FEATURE_FIELDS = (
    _NUMERIC_FIELDS
    + _TIMEFRAME_ONE_HOT_FIELDS
    + _DIRECTION_ONE_HOT_FIELDS
    + _SIGNAL_CLASS_ONE_HOT_FIELDS
    + _DECISION_STATE_ONE_HOT_FIELDS
    + _MARKET_REGIME_ONE_HOT_FIELDS
    + _REGIME_BIAS_ONE_HOT_FIELDS
    + _BINARY_FLAG_FIELDS
)
SIGNAL_MODEL_FEATURE_SCHEMA_VERSION = "1.1"
SIGNAL_MODEL_FEATURE_SCHEMA_HASH = stable_json_hash(
    {
        "schema_kind": "signal_model_feature_vector",
        "schema_version": SIGNAL_MODEL_FEATURE_SCHEMA_VERSION,
        "fields": list(SIGNAL_MODEL_FEATURE_FIELDS),
    }
)
TAKE_TRADE_FEATURE_FIELDS = SIGNAL_MODEL_FEATURE_FIELDS
TAKE_TRADE_FEATURE_SCHEMA_VERSION = SIGNAL_MODEL_FEATURE_SCHEMA_VERSION
TAKE_TRADE_FEATURE_SCHEMA_HASH = SIGNAL_MODEL_FEATURE_SCHEMA_HASH

REGIME_MODEL_FEATURE_FIELDS = tuple(
    f for f in SIGNAL_MODEL_FEATURE_FIELDS if not f.startswith("market_regime_is_")
)
REGIME_MODEL_FEATURE_SCHEMA_HASH = stable_json_hash(
    {
        "schema_kind": "regime_model_feature_vector",
        "schema_version": REGIME_MODEL_FEATURE_SCHEMA_VERSION,
        "fields": list(REGIME_MODEL_FEATURE_FIELDS),
        "excludes": ["market_regime_is_*"],
    }
)


class CalibratedTakeTradeProbModel:
    def __init__(
        self,
        *,
        base_model: Any,
        calibration_method: str,
        calibrator: Any,
    ) -> None:
        self.base_model = base_model
        self.calibration_method = calibration_method
        self.calibrator = calibrator

    def predict_proba(self, X: Any) -> np.ndarray:
        raw = self.base_model.predict_proba(X)
        base_probs = np.asarray(raw, dtype=float)[:, 1]
        calibrated = self._calibrate(base_probs)
        return np.column_stack((1.0 - calibrated, calibrated))

    def _calibrate(self, base_probs: np.ndarray) -> np.ndarray:
        if self.calibration_method == "sigmoid":
            calibrated = self.calibrator.predict_proba(base_probs.reshape(-1, 1))[:, 1]
        elif self.calibration_method == "isotonic":
            calibrated = self.calibrator.predict(base_probs)
        else:
            raise ValueError(f"unsupported calibration_method: {self.calibration_method!r}")
        return np.clip(np.asarray(calibrated, dtype=float), 0.0, 1.0)


class BoundedRegressionModel:
    def __init__(
        self,
        *,
        base_model: Any,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
    ) -> None:
        self.base_model = base_model
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

    def predict(self, X: Any) -> np.ndarray:
        raw = np.asarray(self.base_model.predict(X), dtype=float)
        lower = self.lower_bound if self.lower_bound is not None else -np.inf
        upper = self.upper_bound if self.upper_bound is not None else np.inf
        return np.clip(raw, lower, upper)


def signal_model_feature_contract_descriptor(
    *,
    model_name: str,
    target_field: str,
    model_kind: str,
    output_field: str | None = None,
    calibration_methods: list[str] | None = None,
    scaling_method: str | None = None,
) -> dict[str, Any]:
    out = {
        "model_name": model_name,
        "schema_kind": "signal_model_feature_vector",
        "schema_version": SIGNAL_MODEL_FEATURE_SCHEMA_VERSION,
        "schema_hash": SIGNAL_MODEL_FEATURE_SCHEMA_HASH,
        "fields": list(SIGNAL_MODEL_FEATURE_FIELDS),
        "target_field": target_field,
        "output_field": output_field or target_field,
        "model_kind": model_kind,
    }
    if calibration_methods:
        out["calibration_methods"] = list(calibration_methods)
    if scaling_method:
        out["scaling_method"] = scaling_method
    return out


def take_trade_feature_contract_descriptor() -> dict[str, Any]:
    return signal_model_feature_contract_descriptor(
        model_name=TAKE_TRADE_MODEL_NAME,
        target_field=TAKE_TRADE_TARGET_FIELD,
        output_field=TAKE_TRADE_MODEL_NAME,
        model_kind=TAKE_TRADE_MODEL_KIND,
        calibration_methods=list(TAKE_TRADE_CALIBRATION_METHODS),
    )


def regime_model_feature_contract_descriptor() -> dict[str, Any]:
    return {
        "model_name": MARKET_REGIME_CLASSIFIER_MODEL_NAME,
        "schema_kind": "regime_model_feature_vector",
        "schema_version": REGIME_MODEL_FEATURE_SCHEMA_VERSION,
        "schema_hash": REGIME_MODEL_FEATURE_SCHEMA_HASH,
        "fields": list(REGIME_MODEL_FEATURE_FIELDS),
        "target_field": MARKET_REGIME_TARGET_FIELD,
        "output_field": "predicted_market_regime",
        "model_kind": REGIME_CLASSIFIER_MODEL_KIND,
    }


def build_signal_model_feature_vector(
    *,
    signal_row: Mapping[str, Any] | None,
    feature_snapshot: Mapping[str, Any] | None,
) -> dict[str, float]:
    sig = dict(signal_row or {})
    snapshot = _as_dict(feature_snapshot)
    primary = extract_primary_feature_snapshot(snapshot)
    timeframes = snapshot.get("timeframes")
    tf_rows = timeframes if isinstance(timeframes, dict) else {}

    out: dict[str, float] = {field: math.nan for field in _NUMERIC_FIELDS}
    for field in (
        _TIMEFRAME_ONE_HOT_FIELDS
        + _DIRECTION_ONE_HOT_FIELDS
        + _SIGNAL_CLASS_ONE_HOT_FIELDS
        + _DECISION_STATE_ONE_HOT_FIELDS
        + _MARKET_REGIME_ONE_HOT_FIELDS
        + _REGIME_BIAS_ONE_HOT_FIELDS
        + _BINARY_FLAG_FIELDS
    ):
        out[field] = 0.0

    timeframe = normalize_model_timeframe(str(sig.get("timeframe") or "").strip())
    direction = str(sig.get("direction") or "").strip().lower()
    signal_class = str(sig.get("signal_class") or "").strip().lower()
    decision_state = str(sig.get("decision_state") or "").strip().lower()
    market_regime = normalize_market_regime(sig.get("market_regime")) or "chop"
    regime_bias = normalize_regime_bias(sig.get("regime_bias"), fallback=sig.get("direction")) or "neutral"

    _assign_numeric(out, "signal_strength_0_100", sig.get("signal_strength_0_100"))
    _assign_numeric(out, "heuristic_probability_0_1", sig.get("probability_0_1"))
    _assign_numeric(out, "structure_score_0_100", sig.get("structure_score_0_100"))
    _assign_numeric(out, "momentum_score_layer_0_100", sig.get("momentum_score_0_100"))
    _assign_numeric(out, "multi_timeframe_score_0_100", sig.get("multi_timeframe_score_0_100"))
    _assign_numeric(out, "news_score_0_100", sig.get("news_score_0_100"))
    _assign_numeric(out, "risk_score_0_100", sig.get("risk_score_0_100"))
    _assign_numeric(out, "history_score_0_100", sig.get("history_score_0_100"))
    _assign_numeric(out, "weighted_composite_score_0_100", sig.get("weighted_composite_score_0_100"))
    _assign_numeric(out, "reward_risk_ratio", sig.get("reward_risk_ratio"))
    _assign_numeric(out, "expected_volatility_band", sig.get("expected_volatility_band"))
    _assign_numeric(out, "regime_confidence_0_1", sig.get("regime_confidence_0_1"))

    _assign_numeric(out, "atr_14", primary.get("atr_14"))
    _assign_numeric(out, "atrp_14", primary.get("atrp_14"))
    _assign_numeric(out, "rsi_14", primary.get("rsi_14"))
    _assign_numeric(out, "ret_1", primary.get("ret_1"))
    _assign_numeric(out, "ret_5", primary.get("ret_5"))
    _assign_numeric(out, "momentum_score_feature", primary.get("momentum_score"))
    _assign_numeric(out, "impulse_body_ratio", primary.get("impulse_body_ratio"))
    _assign_numeric(out, "impulse_upper_wick_ratio", primary.get("impulse_upper_wick_ratio"))
    _assign_numeric(out, "impulse_lower_wick_ratio", primary.get("impulse_lower_wick_ratio"))
    _assign_numeric(out, "range_score", primary.get("range_score"))
    _assign_numeric(out, "trend_slope_proxy", primary.get("trend_slope_proxy"))
    _assign_numeric(out, "confluence_score_0_100", primary.get("confluence_score_0_100"))
    _assign_numeric(out, "vol_z_50", primary.get("vol_z_50"))
    _assign_numeric(out, "spread_bps", primary.get("spread_bps"))
    _assign_numeric(out, "depth_balance_ratio", primary.get("depth_balance_ratio"))
    _assign_numeric(out, "depth_to_bar_volume_ratio", primary.get("depth_to_bar_volume_ratio"))
    _assign_numeric(out, "impact_buy_bps_5000", primary.get("impact_buy_bps_5000"))
    _assign_numeric(out, "impact_sell_bps_5000", primary.get("impact_sell_bps_5000"))
    _assign_numeric(out, "execution_cost_bps", primary.get("execution_cost_bps"))
    _assign_numeric(out, "volatility_cost_bps", primary.get("volatility_cost_bps"))
    _assign_numeric(out, "funding_rate_bps", primary.get("funding_rate_bps"))
    _assign_numeric(out, "funding_cost_bps_window", primary.get("funding_cost_bps_window"))
    _assign_numeric(out, "open_interest_change_pct", primary.get("open_interest_change_pct"))
    _assign_numeric(out, "trend_dir_primary", primary.get("trend_dir"))

    for tf in MODEL_TIMEFRAMES:
        tf_row = tf_rows.get(tf)
        _assign_numeric(out, f"trend_dir_{tf}", _feature_value(tf_row, "trend_dir"))

    out["high_tf_alignment_ratio"] = _alignment_ratio(tf_rows, regime_bias, direction)
    if timeframe in MODEL_TIMEFRAMES:
        out[f"timeframe_is_{timeframe}"] = 1.0
    if direction in ("long", "short", "neutral"):
        out[f"direction_is_{direction}"] = 1.0
    if signal_class in ("mikro", "kern", "gross", "warnung"):
        out[f"signal_class_is_{signal_class}"] = 1.0
    if decision_state in ("accepted", "downgraded", "rejected"):
        out[f"decision_state_is_{decision_state}"] = 1.0
    out[f"market_regime_is_{market_regime}"] = 1.0
    out[f"regime_bias_is_{regime_bias}"] = 1.0

    liquidity_source = str(primary.get("liquidity_source") or "").strip()
    out["liquidity_source_orderbook_levels"] = 1.0 if liquidity_source == "orderbook_levels" else 0.0
    out["liquidity_source_fallback"] = (
        1.0 if liquidity_source not in ("", "orderbook_levels", "missing") else 0.0
    )
    out["funding_source_present"] = 1.0 if str(primary.get("funding_source") or "").strip() else 0.0
    out["open_interest_source_present"] = (
        1.0 if str(primary.get("open_interest_source") or "").strip() else 0.0
    )
    return out


def build_take_trade_feature_vector(
    *,
    signal_row: Mapping[str, Any] | None,
    feature_snapshot: Mapping[str, Any] | None,
) -> dict[str, float]:
    return build_signal_model_feature_vector(
        signal_row=signal_row,
        feature_snapshot=feature_snapshot,
    )


def build_signal_model_feature_vector_from_evaluation(row: Mapping[str, Any]) -> dict[str, float]:
    return build_signal_model_feature_vector(
        signal_row=_as_dict(row.get("signal_snapshot_json")),
        feature_snapshot=_as_dict(row.get("feature_snapshot_json")),
    )


def build_signal_model_feature_reference(
    examples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    numeric_fields: dict[str, dict[str, float | int]] = {}
    for field in _NUMERIC_FIELDS:
        values: list[float] = []
        for example in examples:
            feature_map = example.get("features")
            if not isinstance(feature_map, Mapping):
                continue
            numeric = _coerce_float(feature_map.get(field))
            if numeric is None or not math.isfinite(numeric):
                continue
            values.append(numeric)
        if len(values) < 12:
            continue
        arr = np.asarray(values, dtype=float)
        q05, q25, q50, q75, q95 = np.quantile(arr, [0.05, 0.25, 0.50, 0.75, 0.95])
        numeric_fields[field] = {
            "count": int(arr.size),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p05": float(q05),
            "p25": float(q25),
            "p50": float(q50),
            "p75": float(q75),
            "p95": float(q95),
            "iqr": float(max(q75 - q25, 1e-6)),
        }
    return {
        "schema_kind": "signal_model_feature_reference",
        "schema_hash": SIGNAL_MODEL_FEATURE_SCHEMA_HASH,
        "numeric_fields": numeric_fields,
    }


def evaluate_signal_model_ood(
    *,
    features: Mapping[str, Any],
    feature_reference: Mapping[str, Any] | None,
    robust_z_threshold: float,
    max_flagged_features: int,
) -> dict[str, Any]:
    if not isinstance(feature_reference, Mapping):
        return {
            "ood_score_0_1": 1.0,
            "ood_alert": True,
            "flagged_features": [],
            "compared_features": 0,
            "reasons_json": ["missing_feature_reference"],
        }
    ref_fields = feature_reference.get("numeric_fields")
    if not isinstance(ref_fields, Mapping) or not ref_fields:
        return {
            "ood_score_0_1": 1.0,
            "ood_alert": True,
            "flagged_features": [],
            "compared_features": 0,
            "reasons_json": ["empty_feature_reference"],
        }
    flagged: list[dict[str, Any]] = []
    compared = 0
    max_distance = 0.0
    for field, raw_stats in ref_fields.items():
        if not isinstance(raw_stats, Mapping):
            continue
        numeric = _coerce_float(features.get(field))
        if numeric is None or not math.isfinite(numeric):
            continue
        compared += 1
        p05 = _coerce_float(raw_stats.get("p05"))
        p95 = _coerce_float(raw_stats.get("p95"))
        iqr = _coerce_float(raw_stats.get("iqr"))
        if p05 is None or p95 is None or iqr is None:
            continue
        distance = 0.0
        edge = None
        if numeric < p05:
            distance = (p05 - numeric) / max(iqr, 1e-6)
            edge = "low"
        elif numeric > p95:
            distance = (numeric - p95) / max(iqr, 1e-6)
            edge = "high"
        max_distance = max(max_distance, distance)
        if distance >= robust_z_threshold:
            flagged.append(
                {
                    "field": field,
                    "value": numeric,
                    "edge": edge,
                    "distance": float(distance),
                    "p05": p05,
                    "p95": p95,
                }
            )
    flagged_count = len(flagged)
    severe_outlier = max_distance >= robust_z_threshold * 1.5
    ood_alert = severe_outlier or flagged_count >= max_flagged_features
    fraction_score = 0.0
    if compared > 0 and max_flagged_features > 0:
        fraction_score = min(1.0, flagged_count / float(max_flagged_features))
    distance_score = min(1.0, max_distance / max(robust_z_threshold, 1e-6))
    reasons = [f"ood_feature:{item['field']}" for item in flagged[:8]]
    if severe_outlier:
        reasons.append("ood_extreme_outlier")
    return {
        "ood_score_0_1": max(distance_score, fraction_score),
        "ood_alert": bool(ood_alert),
        "flagged_features": flagged,
        "compared_features": compared,
        "reasons_json": reasons,
    }


def build_take_trade_feature_vector_from_evaluation(row: Mapping[str, Any]) -> dict[str, float]:
    return build_signal_model_feature_vector_from_evaluation(row)


def build_regime_model_feature_vector_from_evaluation(row: Mapping[str, Any]) -> dict[str, float]:
    full = build_signal_model_feature_vector_from_evaluation(row)
    return {field: float(full.get(field, math.nan)) for field in REGIME_MODEL_FEATURE_FIELDS}


def build_regime_model_feature_reference(
    examples: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    numeric_fields: dict[str, dict[str, float | int]] = {}
    for field in _NUMERIC_FIELDS:
        if field not in REGIME_MODEL_FEATURE_FIELDS:
            continue
        values: list[float] = []
        for example in examples:
            feature_map = example.get("features")
            if not isinstance(feature_map, Mapping):
                continue
            numeric = _coerce_float(feature_map.get(field))
            if numeric is None or not math.isfinite(numeric):
                continue
            values.append(numeric)
        if len(values) < 12:
            continue
        arr = np.asarray(values, dtype=float)
        q05, q25, q50, q75, q95 = np.quantile(arr, [0.05, 0.25, 0.50, 0.75, 0.95])
        numeric_fields[field] = {
            "count": int(arr.size),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p05": float(q05),
            "p25": float(q25),
            "p50": float(q50),
            "p75": float(q75),
            "p95": float(q95),
            "iqr": float(max(q75 - q25, 1e-6)),
        }
    return {
        "schema_kind": "regime_model_feature_reference",
        "schema_hash": REGIME_MODEL_FEATURE_SCHEMA_HASH,
        "numeric_fields": numeric_fields,
    }


def _feature_value(row: Any, field: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(field)
    return None


def _assign_numeric(out: dict[str, float], field: str, value: Any) -> None:
    numeric = _coerce_float(value)
    out[field] = numeric if numeric is not None else math.nan


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _alignment_ratio(
    tf_rows: Mapping[str, Any],
    regime_bias: str,
    direction: str,
) -> float:
    want = 1 if regime_bias == "long" else -1 if regime_bias == "short" else 0
    if want == 0:
        want = 1 if direction == "long" else -1 if direction == "short" else 0
    if want == 0:
        return 0.0
    votes = 0
    aligned = 0
    for tf in ("15m", "1H", "4H"):
        row = tf_rows.get(tf)
        numeric = _coerce_float(_feature_value(row, "trend_dir"))
        if numeric is None or numeric == 0:
            continue
        votes += 1
        if int(math.copysign(1, numeric)) == want:
            aligned += 1
    if votes == 0:
        return 0.0
    return aligned / votes
