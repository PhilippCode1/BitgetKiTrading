"""
Governance-Artefakte pro Trainingslauf: Lineage, Feature-Schema, Manifest-Zeiger,
Kalibrierungsnachweis. Optionale Promotion-Saeule (ENV-gesteuert).
"""

from __future__ import annotations

import json
from typing import Any

from shared_py.model_registry_policy import (
    model_requires_probability_calibration,
    parse_metadata_json,
)

from learning_engine.config import LearningEngineSettings


def _as_metrics_dict(raw: Any) -> dict[str, Any]:
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


def _non_empty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _calibration_evidence_present(
    *, metadata: dict[str, Any], metrics: dict[str, Any]
) -> bool:
    cc_m = metrics.get("calibration_curve")
    cc_meta = metadata.get("calibration_curve")
    if isinstance(cc_m, list | dict) and len(cc_m) > 0:
        return True
    if isinstance(cc_meta, list | dict) and len(cc_meta) > 0:
        return True
    brier = metrics.get("brier_score")
    try:
        return brier is not None and 0 <= float(brier) <= 1.0
    except (TypeError, ValueError):
        return False


def evaluate_training_run_governance(
    *,
    model_name: str,
    metadata_json: Any,
    metrics_json: Any,
    settings: LearningEngineSettings,
) -> tuple[bool, tuple[str, ...], dict[str, Any]]:
    if not settings.model_promotion_require_governance_artifacts:
        return True, (), {"skipped": True}

    meta = parse_metadata_json(metadata_json)
    metrics = _as_metrics_dict(metrics_json)
    reasons: list[str] = []
    details: dict[str, Any] = {"model_name": model_name}

    if not _non_empty_str(meta.get("data_version_hash")):
        reasons.append("governance_data_version_hash_missing")
    if not _non_empty_str(meta.get("dataset_hash")):
        reasons.append("governance_dataset_hash_missing")

    fc = meta.get("feature_contract")
    if not isinstance(fc, dict) or not _non_empty_str(fc.get("schema_hash")):
        reasons.append("governance_feature_schema_hash_missing")

    af = meta.get("artifact_files")
    tm = af.get("training_manifest") if isinstance(af, dict) else None
    if not isinstance(af, dict) or not _non_empty_str(tm):
        reasons.append("governance_training_manifest_ref_missing")

    if model_requires_probability_calibration(model_name):
        if not _calibration_evidence_present(metadata=meta, metrics=metrics):
            reasons.append("governance_calibration_evidence_missing")

    fb = meta.get("inference_fallback_policy")
    if settings.model_promotion_require_inference_behavior_metadata:
        if not isinstance(fb, dict) or not str(fb.get("mode") or "").strip():
            reasons.append("governance_inference_fallback_policy_missing")
        abst = meta.get("inference_abstention_policy")
        if not isinstance(abst, dict) or not str(abst.get("summary") or "").strip():
            reasons.append("governance_inference_abstention_policy_missing")

    ok = len(reasons) == 0
    return ok, tuple(reasons), details


def parse_online_drift_promotion_block_tiers(
    settings: LearningEngineSettings,
) -> frozenset[str]:
    csv = settings.model_promotion_online_drift_blocked_tiers_csv or ""
    raw = csv.strip().lower()
    parts = {p.strip() for p in raw.split(",") if p.strip()}
    allowed = {"warn", "shadow_only", "hard_block"}
    return frozenset(p for p in parts if p in allowed)
