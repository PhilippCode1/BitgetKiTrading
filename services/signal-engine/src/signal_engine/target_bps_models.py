from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from joblib import load

from shared_py.model_contracts import extract_primary_feature_snapshot
from shared_py.projection_adjustment import apply_projection_cost_adjustment
from shared_py.take_trade_model import (
    EXPECTED_MAE_BPS_MODEL_NAME,
    EXPECTED_MFE_BPS_MODEL_NAME,
    EXPECTED_RETURN_BPS_MODEL_NAME,
    SIGNAL_MODEL_FEATURE_FIELDS,
    build_signal_model_feature_vector,
    evaluate_signal_model_ood,
)
from signal_engine.storage.repo import SignalRepository


@dataclass(frozen=True)
class _BpsProjectionSpec:
    model_name: str
    output_field: str
    target_field: str


_BPS_PROJECTION_SPECS = (
    _BpsProjectionSpec(
        model_name=EXPECTED_RETURN_BPS_MODEL_NAME,
        output_field="expected_return_bps",
        target_field="expected_return_bps",
    ),
    _BpsProjectionSpec(
        model_name=EXPECTED_MAE_BPS_MODEL_NAME,
        output_field="expected_mae_bps",
        target_field="expected_mae_bps",
    ),
    _BpsProjectionSpec(
        model_name=EXPECTED_MFE_BPS_MODEL_NAME,
        output_field="expected_mfe_bps",
        target_field="expected_mfe_bps",
    ),
)


class TargetBpsModelScorer:
    def __init__(
        self,
        repo: SignalRepository,
        *,
        refresh_ms: int,
        ood_robust_z_threshold: float,
        ood_max_flagged_features: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._scorers = {
            spec.output_field: _ScalarRegressionModelScorer(
                repo,
                spec=spec,
                refresh_ms=refresh_ms,
                ood_robust_z_threshold=ood_robust_z_threshold,
                ood_max_flagged_features=ood_max_flagged_features,
                logger=logger,
            )
            for spec in _BPS_PROJECTION_SPECS
        }

    def predict(
        self,
        *,
        signal_row: dict[str, Any],
        feature_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        features = build_signal_model_feature_vector(
            signal_row=signal_row,
            feature_snapshot=feature_snapshot,
        )
        matrix = [[features[field] for field in SIGNAL_MODEL_FEATURE_FIELDS]]
        outputs: dict[str, Any] = {
            "expected_return_bps": None,
            "expected_mae_bps": None,
            "expected_mfe_bps": None,
            "target_projection_adjusted": None,
            "target_projection_models_json": [],
            "target_projection_summary": None,
            "target_projection_diagnostics": {
                "ood_score_0_1": 1.0,
                "ood_alert": True,
                "ood_reasons_json": ["missing_target_projection_models"],
                "max_bound_proximity_0_1": None,
            },
        }
        model_rows: list[dict[str, Any]] = []
        diagnostics_rows: list[dict[str, Any]] = []
        for spec in _BPS_PROJECTION_SPECS:
            value, summary, diagnostics = self._scorers[spec.output_field].predict(matrix, features)
            outputs[spec.output_field] = value
            if summary is not None:
                model_rows.append(summary)
            if diagnostics is not None:
                diagnostics_rows.append(diagnostics)
        outputs["target_projection_models_json"] = model_rows
        _apply_cost_adjustment_to_outputs(outputs, signal_row=signal_row, feature_snapshot=feature_snapshot)
        outputs["target_projection_summary"] = _projection_summary(outputs)
        outputs["target_projection_diagnostics"] = _aggregate_diagnostics(diagnostics_rows)
        return outputs


class _ScalarRegressionModelScorer:
    def __init__(
        self,
        repo: SignalRepository,
        *,
        spec: _BpsProjectionSpec,
        refresh_ms: int,
        ood_robust_z_threshold: float,
        ood_max_flagged_features: int,
        logger: logging.Logger | None = None,
    ) -> None:
        self._repo = repo
        self._spec = spec
        self._refresh_ms = refresh_ms
        self._ood_robust_z_threshold = ood_robust_z_threshold
        self._ood_max_flagged_features = ood_max_flagged_features
        self._logger = logger or logging.getLogger("signal_engine.target_bps_models")
        self._last_refresh_ms = 0
        self._loaded_run_id: str | None = None
        self._loaded_model: Any | None = None
        self._loaded_row: dict[str, Any] | None = None

    def predict(
        self,
        matrix: list[list[float]],
        features: dict[str, float],
    ) -> tuple[float | None, dict[str, Any] | None, dict[str, Any] | None]:
        self._maybe_refresh()
        if self._loaded_model is None or self._loaded_row is None:
            return None, None, {
                "model_name": self._spec.model_name,
                "ood_score_0_1": 1.0,
                "ood_alert": True,
                "ood_reasons_json": [f"missing_{self._spec.model_name}_model"],
                "bound_proximity_0_1": None,
            }
        value = float(self._loaded_model.predict(matrix)[0])
        diagnostics = _inference_diagnostics(
            spec=self._spec,
            row=self._loaded_row,
            features=features,
            prediction=value,
            robust_z_threshold=self._ood_robust_z_threshold,
            max_flagged_features=self._ood_max_flagged_features,
        )
        return value, _metadata_summary(self._spec, self._loaded_row, diagnostics), diagnostics

    def _maybe_refresh(self) -> None:
        now_ms = int(time.time() * 1000)
        if self._last_refresh_ms and now_ms - self._last_refresh_ms < self._refresh_ms:
            return
        self._last_refresh_ms = now_ms
        row = self._repo.fetch_production_model_run(model_name=self._spec.model_name)
        if row is None:
            self._loaded_run_id = None
            self._loaded_model = None
            self._loaded_row = None
            return
        run_id = str(row.get("run_id") or "").strip() or None
        if self._loaded_run_id == run_id and self._loaded_model is not None:
            return
        artifact_path = _resolve_artifact_path(row.get("artifact_path"))
        if artifact_path is None or not artifact_path.is_file():
            self._logger.warning(
                "target_bps_model artifact fehlt model=%s path=%s",
                self._spec.model_name,
                row.get("artifact_path"),
            )
            self._loaded_run_id = None
            self._loaded_model = None
            self._loaded_row = None
            return
        try:
            self._loaded_model = load(artifact_path)
            self._loaded_row = row
            self._loaded_run_id = run_id
        except Exception as exc:
            self._logger.warning("target_bps_model load failed model=%s: %s", self._spec.model_name, exc)
            self._loaded_run_id = None
            self._loaded_model = None
            self._loaded_row = None


def _apply_cost_adjustment_to_outputs(
    outputs: dict[str, Any],
    *,
    signal_row: dict[str, Any],
    feature_snapshot: dict[str, Any] | None,
) -> None:
    raw_r = _coerce_float(outputs.get("expected_return_bps"))
    raw_a = _coerce_float(outputs.get("expected_mae_bps"))
    raw_f = _coerce_float(outputs.get("expected_mfe_bps"))
    if raw_r is None and raw_a is None and raw_f is None:
        outputs["target_projection_adjusted"] = None
        return
    primary = extract_primary_feature_snapshot(feature_snapshot)
    adj = apply_projection_cost_adjustment(
        raw_return_bps=raw_r,
        raw_mae_bps=raw_a,
        raw_mfe_bps=raw_f,
        direction=str(signal_row.get("direction") or ""),
        primary_tf=primary,
    )
    outputs["target_projection_adjusted"] = adj
    eff = adj.get("effective_bps") if isinstance(adj, dict) else None
    if isinstance(eff, dict):
        for key in ("expected_return_bps", "expected_mae_bps", "expected_mfe_bps"):
            v = _coerce_float(eff.get(key))
            if v is not None:
                outputs[key] = v


def _projection_summary(outputs: dict[str, Any]) -> dict[str, Any] | None:
    expected_return = _coerce_float(outputs.get("expected_return_bps"))
    expected_mae = _coerce_float(outputs.get("expected_mae_bps"))
    expected_mfe = _coerce_float(outputs.get("expected_mfe_bps"))
    if expected_return is None and expected_mae is None and expected_mfe is None:
        return None
    reward_to_adverse = None
    if expected_mae is not None and expected_mfe is not None:
        reward_to_adverse = expected_mfe / max(expected_mae, 1.0)
    net_edge_to_adverse = None
    if expected_return is not None and expected_mae is not None:
        net_edge_to_adverse = expected_return / max(expected_mae, 1.0)
    out: dict[str, Any] = {
        "expected_return_bps": expected_return,
        "expected_mae_bps": expected_mae,
        "expected_mfe_bps": expected_mfe,
        "reward_to_adverse_ratio": reward_to_adverse,
        "net_edge_to_adverse_ratio": net_edge_to_adverse,
    }
    adj = outputs.get("target_projection_adjusted")
    if isinstance(adj, dict) and adj.get("model_raw_bps"):
        out["model_raw_bps"] = adj["model_raw_bps"]
        out["round_trip_cost_bps"] = adj.get("round_trip_cost_bps")
        out["safety_stop_buffer_bps"] = adj.get("safety_stop_buffer_bps")
    return out


def _resolve_artifact_path(raw_path: Any) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[4] / path


def _metadata_summary(
    spec: _BpsProjectionSpec,
    row: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    metadata = _metadata_json(row)
    metrics = row.get("metrics_json")
    if isinstance(metrics, str):
        try:
            metrics = json.loads(metrics)
        except json.JSONDecodeError:
            metrics = {}
    if not isinstance(metrics, dict):
        metrics = {}
    feature_contract = metadata.get("feature_contract")
    feature_schema_hash = None
    if isinstance(feature_contract, dict):
        feature_schema_hash = feature_contract.get("schema_hash")
    return {
        "model_name": row.get("model_name"),
        "version": row.get("version"),
        "run_id": str(row.get("run_id")) if row.get("run_id") is not None else None,
        "output_field": spec.output_field,
        "target_field": spec.target_field,
        "scaling_method": metadata.get("scaling_method"),
        "dataset_hash": row.get("dataset_hash"),
        "feature_schema_hash": feature_schema_hash,
        "trained_at_ms": metadata.get("trained_at_ms"),
        "regime_counts_train": metadata.get("regime_counts_train"),
        "prediction_lower_bound_bps": metadata.get("prediction_lower_bound_bps"),
        "prediction_upper_bound_bps": metadata.get("prediction_upper_bound_bps"),
        "ood_score_0_1": diagnostics.get("ood_score_0_1"),
        "ood_alert": diagnostics.get("ood_alert"),
        "ood_reasons_json": diagnostics.get("ood_reasons_json"),
        "bound_proximity_0_1": diagnostics.get("bound_proximity_0_1"),
        "metrics": {
            "mae_bps": metrics.get("mae_bps"),
            "rmse_bps": metrics.get("rmse_bps"),
            "median_absolute_error_bps": metrics.get("median_absolute_error_bps"),
        },
    }


def _inference_diagnostics(
    *,
    spec: _BpsProjectionSpec,
    row: dict[str, Any],
    features: dict[str, float],
    prediction: float,
    robust_z_threshold: float,
    max_flagged_features: int,
) -> dict[str, Any]:
    metadata = _metadata_json(row)
    ood = evaluate_signal_model_ood(
        features=features,
        feature_reference=metadata.get("feature_reference"),
        robust_z_threshold=robust_z_threshold,
        max_flagged_features=max_flagged_features,
    )
    return {
        "model_name": spec.model_name,
        "ood_score_0_1": ood["ood_score_0_1"],
        "ood_alert": ood["ood_alert"],
        "ood_reasons_json": ood["reasons_json"],
        "bound_proximity_0_1": _bound_proximity(
            prediction=prediction,
            lower_bound=_coerce_float(metadata.get("prediction_lower_bound_bps")),
            upper_bound=_coerce_float(metadata.get("prediction_upper_bound_bps")),
        ),
    }


def _aggregate_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "ood_score_0_1": 1.0,
            "ood_alert": True,
            "ood_reasons_json": ["missing_target_projection_models"],
            "max_bound_proximity_0_1": None,
        }
    ood_score = max(float(row.get("ood_score_0_1") or 0.0) for row in rows)
    ood_alert = any(bool(row.get("ood_alert")) for row in rows)
    reasons: list[str] = []
    for row in rows:
        for reason in row.get("ood_reasons_json") or []:
            if isinstance(reason, str) and reason not in reasons:
                reasons.append(reason)
    bound_values = [_coerce_float(row.get("bound_proximity_0_1")) for row in rows]
    finite_bounds = [value for value in bound_values if value is not None]
    return {
        "ood_score_0_1": ood_score,
        "ood_alert": ood_alert,
        "ood_reasons_json": reasons,
        "max_bound_proximity_0_1": max(finite_bounds) if finite_bounds else None,
    }


def _bound_proximity(
    *,
    prediction: float,
    lower_bound: float | None,
    upper_bound: float | None,
) -> float | None:
    if lower_bound is None or upper_bound is None or upper_bound <= lower_bound:
        return None
    span = max(upper_bound - lower_bound, 1e-6)
    edge_band = span * 0.10
    distance = min(prediction - lower_bound, upper_bound - prediction)
    if distance >= edge_band:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (distance / max(edge_band, 1e-6))))


def _metadata_json(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata_json")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
