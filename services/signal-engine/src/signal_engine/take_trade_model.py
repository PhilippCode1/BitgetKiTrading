from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from joblib import load

from shared_py.take_trade_model import (
    TAKE_TRADE_FEATURE_FIELDS,
    TAKE_TRADE_MODEL_NAME,
    build_take_trade_feature_vector,
    evaluate_signal_model_ood,
)
from signal_engine.storage.repo import SignalRepository


class TakeTradeModelScorer:
    def __init__(
        self,
        repo: SignalRepository,
        *,
        refresh_ms: int,
        ood_robust_z_threshold: float,
        ood_max_flagged_features: int,
        logger: logging.Logger | None = None,
        registry_scoped_slots_enabled: bool = False,
    ) -> None:
        self._repo = repo
        self._refresh_ms = refresh_ms
        self._ood_robust_z_threshold = ood_robust_z_threshold
        self._ood_max_flagged_features = ood_max_flagged_features
        self._registry_scoped_slots_enabled = registry_scoped_slots_enabled
        self._logger = logger or logging.getLogger("signal_engine.take_trade_model")
        self._last_refresh_ms = 0
        self._last_resolution_key: str | None = None
        self._loaded_run_id: str | None = None
        self._loaded_model: Any | None = None
        self._loaded_row: dict[str, Any] | None = None

    def predict(
        self,
        *,
        signal_row: dict[str, Any],
        feature_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self._maybe_refresh(signal_row)
        if self._loaded_model is None or self._loaded_row is None:
            return {
                "take_trade_prob": None,
                "take_trade_model_version": None,
                "take_trade_model_run_id": None,
                "take_trade_calibration_method": None,
                "take_trade_model_info": None,
                "take_trade_model_diagnostics": {
                    "confidence_0_1": None,
                    "ood_score_0_1": 1.0,
                    "ood_alert": True,
                    "ood_reasons_json": ["missing_take_trade_model"],
                    "flagged_features": [],
                },
            }

        features = build_take_trade_feature_vector(
            signal_row=signal_row,
            feature_snapshot=feature_snapshot,
        )
        matrix = [[features[field] for field in TAKE_TRADE_FEATURE_FIELDS]]
        probability = float(self._loaded_model.predict_proba(matrix)[0][1])
        metadata = _metadata_summary(self._loaded_row)
        cal_method = str(self._loaded_row.get("calibration_method") or "").strip() or None
        diagnostics = _inference_diagnostics(
            row=self._loaded_row,
            features=features,
            probability=probability,
            robust_z_threshold=self._ood_robust_z_threshold,
            max_flagged_features=self._ood_max_flagged_features,
            calibration_method=cal_method,
        )
        return {
            "take_trade_prob": probability,
            "take_trade_model_version": str(self._loaded_row.get("version") or "").strip() or None,
            "take_trade_model_run_id": str(self._loaded_row.get("run_id") or "").strip() or None,
            "take_trade_calibration_method": str(
                self._loaded_row.get("calibration_method") or ""
            ).strip()
            or None,
            "take_trade_model_info": metadata,
            "take_trade_model_diagnostics": diagnostics,
        }

    def _registry_resolution_key(self, signal_row: dict[str, Any] | None) -> str:
        if not self._registry_scoped_slots_enabled or not signal_row:
            return "global"
        mf = str(signal_row.get("market_family") or "").strip().lower()
        mr = str(signal_row.get("market_regime") or "").strip().lower()
        pb = str(signal_row.get("playbook_id") or "").strip()
        sym = str(signal_row.get("symbol") or "").strip().upper()
        return f"{mf}|{mr}|{pb}|{sym}"

    def _maybe_refresh(self, signal_row: dict[str, Any] | None = None) -> None:
        now_ms = int(time.time() * 1000)
        res_key = self._registry_resolution_key(signal_row)
        within_ttl = self._last_refresh_ms and now_ms - self._last_refresh_ms < self._refresh_ms
        if within_ttl and res_key == self._last_resolution_key:
            return
        if not within_ttl:
            self._last_refresh_ms = now_ms
        self._last_resolution_key = res_key
        mf = mr = pb = sym = None
        if self._registry_scoped_slots_enabled and signal_row:
            mf = str(signal_row.get("market_family") or "").strip().lower() or None
            mr = str(signal_row.get("market_regime") or "").strip().lower() or None
            pb = str(signal_row.get("playbook_id") or "").strip() or None
            sym = str(signal_row.get("symbol") or "").strip().upper() or None
        row = self._repo.fetch_production_model_run(
            model_name=TAKE_TRADE_MODEL_NAME,
            market_family=mf,
            market_regime=mr,
            playbook_id=pb,
            router_slot=None,
            symbol=sym,
        )
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
            self._logger.warning("take_trade_model artifact fehlt: %s", row.get("artifact_path"))
            self._loaded_run_id = None
            self._loaded_model = None
            self._loaded_row = None
            return
        try:
            self._loaded_model = load(artifact_path)
            self._loaded_row = row
            self._loaded_run_id = run_id
        except Exception as exc:
            self._logger.warning("take_trade_model load failed: %s", exc)
            self._loaded_run_id = None
            self._loaded_model = None
            self._loaded_row = None


def _resolve_artifact_path(raw_path: Any) -> Path | None:
    value = str(raw_path or "").strip()
    if not value:
        return None
    path = Path(value)
    if path.is_absolute():
        return path
    return Path(__file__).resolve().parents[4] / path


def _metadata_summary(row: dict[str, Any]) -> dict[str, Any]:
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
    out: dict[str, Any] = {
        "model_name": row.get("model_name"),
        "version": row.get("version"),
        "run_id": str(row.get("run_id")) if row.get("run_id") is not None else None,
        "calibration_method": row.get("calibration_method"),
        "dataset_hash": row.get("dataset_hash"),
        "feature_schema_hash": feature_schema_hash,
        "trained_at_ms": metadata.get("trained_at_ms"),
        "regime_counts_train": metadata.get("regime_counts_train"),
        "metrics": {
            "brier_score": metrics.get("brier_score"),
            "roc_auc": metrics.get("roc_auc"),
            "average_precision": metrics.get("average_precision"),
        },
    }
    if row.get("registry_role"):
        out["registry_role"] = row.get("registry_role")
        out["registry_calibration_status"] = row.get("registry_calibration_status")
        out["registry_activated_ts"] = row.get("registry_activated_ts")
    return out


def _inference_diagnostics(
    *,
    row: dict[str, Any],
    features: dict[str, float],
    probability: float,
    robust_z_threshold: float,
    max_flagged_features: int,
    calibration_method: str | None = None,
) -> dict[str, Any]:
    metadata = _metadata_json(row)
    ood = evaluate_signal_model_ood(
        features=features,
        feature_reference=metadata.get("feature_reference"),
        robust_z_threshold=robust_z_threshold,
        max_flagged_features=max_flagged_features,
    )
    return {
        "confidence_0_1": abs(probability - 0.5) * 2.0,
        "calibration_method": calibration_method,
        "ood_score_0_1": ood["ood_score_0_1"],
        "ood_alert": ood["ood_alert"],
        "ood_reasons_json": ood["reasons_json"],
        "flagged_features": ood["flagged_features"],
    }


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
