"""
Produktionsregeln fuer Model Registry V2 und Kalibrierungspflicht.
"""

from __future__ import annotations

from typing import Any

from shared_py.take_trade_model import (
    MARKET_REGIME_CLASSIFIER_MODEL_NAME,
    TAKE_TRADE_MODEL_NAME,
)

PROBABILITY_MODEL_NAMES_REQUIRING_CALIBRATION = frozenset(
    {
        TAKE_TRADE_MODEL_NAME,
        MARKET_REGIME_CLASSIFIER_MODEL_NAME,
    }
)


def model_requires_probability_calibration(model_name: str) -> bool:
    return model_name.strip() in PROBABILITY_MODEL_NAMES_REQUIRING_CALIBRATION


def parse_metadata_json(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        import json

        try:
            out = json.loads(raw)
            return out if isinstance(out, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def production_probability_calibration_satisfied(
    *,
    model_name: str,
    calibration_method: str | None,
    metadata_json: Any,
) -> bool:
    if not model_requires_probability_calibration(model_name):
        return True
    cal = (str(calibration_method or "")).strip().lower()
    if cal not in ("sigmoid", "isotonic"):
        return False
    meta = parse_metadata_json(metadata_json)
    artifacts = meta.get("artifact_files")
    if isinstance(artifacts, dict) and str(artifacts.get("calibration") or "").strip():
        return True
    if str(meta.get("calibration_method") or "").strip().lower() in ("sigmoid", "isotonic"):
        return True
    return cal in ("sigmoid", "isotonic")


def champion_assignment_calibration_ok(
    *,
    model_name: str,
    calibration_required: bool,
    calibration_method: str | None,
    metadata_json: Any,
) -> bool:
    if not calibration_required:
        return True
    return production_probability_calibration_satisfied(
        model_name=model_name,
        calibration_method=calibration_method,
        metadata_json=metadata_json,
    )
