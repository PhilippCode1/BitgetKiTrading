"""
Kanonischer Datenvertrag fuer die Modellschicht (Training + Inferenz).

Verknuepft:
- Roh-Feature-Snapshot (model_contracts / Feature-Engine)
- abgeleiteten Signal-Modell-Vektor (take_trade_model)

Felder des Vektors sind mit Tier required / optional / experimentell katalogisiert.
Der Katalog ist separat versioniert (field_catalog_version + Hash), ohne den
bestehenden SIGNAL_MODEL_FEATURE_SCHEMA_HASH zu aendern.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping

from shared_py.model_contracts import (
    FEATURE_SCHEMA_HASH,
    FEATURE_SCHEMA_VERSION,
    MODEL_CONTRACT_VERSION,
    stable_json_hash,
)
from shared_py.take_trade_model import (
    SIGNAL_MODEL_FEATURE_FIELDS,
    SIGNAL_MODEL_FEATURE_SCHEMA_HASH,
    SIGNAL_MODEL_FEATURE_SCHEMA_VERSION,
)

MODEL_LAYER_CONTRACT_VERSION = "1.0"

FeatureTier = Literal["required", "optional", "experimental"]

# Mikrostruktur, Impact, Funding-Fenster, OI-Delta — duerfen fehlen (NaN), ohne Zeile zu verwerfen.
_OPTIONAL_SIGNAL_FIELDS: frozenset[str] = frozenset(
    {
        "atrp_14",
        "structure_score_0_100",
        "momentum_score_layer_0_100",
        "multi_timeframe_score_0_100",
        "risk_score_0_100",
        "weighted_composite_score_0_100",
        "reward_risk_ratio",
        "expected_volatility_band",
        "regime_confidence_0_1",
        "momentum_score_feature",
        "impulse_body_ratio",
        "vol_z_50",
        "spread_bps",
        "depth_balance_ratio",
        "funding_rate_bps",
        "trend_slope_proxy",
        "confluence_score_0_100",
        "range_score",
        "trend_dir_1m",
        "trend_dir_5m",
        "trend_dir_15m",
        "trend_dir_1H",
        "trend_dir_4H",
        "high_tf_alignment_ratio",
    }
)

# Duenne oder instabile Signale; nicht fuer harte Qualitaets-Gates in Produktion.
_EXPERIMENTAL_SIGNAL_FIELDS: frozenset[str] = frozenset(
    {
        "news_score_0_100",
        "history_score_0_100",
        "impulse_upper_wick_ratio",
        "impulse_lower_wick_ratio",
        "depth_to_bar_volume_ratio",
        "impact_buy_bps_5000",
        "impact_sell_bps_5000",
        "execution_cost_bps",
        "volatility_cost_bps",
        "funding_cost_bps_window",
        "open_interest_change_pct",
    }
)

# Modell-Outputs / Zielgroessen, die im Entscheidungs-Snapshot nicht vorkommen duerfen (Leakage).
LEAK_PRONE_SIGNAL_SNAPSHOT_KEYS: frozenset[str] = frozenset(
    {
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
    }
)


def signal_feature_tier(field: str) -> FeatureTier:
    if field in _EXPERIMENTAL_SIGNAL_FIELDS:
        return "experimental"
    if field in _OPTIONAL_SIGNAL_FIELDS:
        return "optional"
    return "required"


def build_signal_field_catalog() -> dict[str, FeatureTier]:
    return {field: signal_feature_tier(field) for field in SIGNAL_MODEL_FEATURE_FIELDS}


_SIGNAL_FIELD_CATALOG = build_signal_field_catalog()

_OPTIONAL_EXPERIMENTAL = _OPTIONAL_SIGNAL_FIELDS | _EXPERIMENTAL_SIGNAL_FIELDS
_CATALOG_KEYS = set(_SIGNAL_FIELD_CATALOG.keys())
_VECTOR_FIELDS_SET = set(SIGNAL_MODEL_FEATURE_FIELDS)
if _CATALOG_KEYS != _VECTOR_FIELDS_SET:
    raise RuntimeError("SIGNAL_MODEL_FIELD_KATALOG passt nicht zu SIGNAL_MODEL_FEATURE_FIELDS")
if not _OPTIONAL_EXPERIMENTAL <= _VECTOR_FIELDS_SET:
    raise RuntimeError("optional/experimentell enthaelt unbekannte Felder")
if _OPTIONAL_SIGNAL_FIELDS & _EXPERIMENTAL_SIGNAL_FIELDS:
    raise RuntimeError("Schnittmenge optional/experimentell muss leer sein")

FIELD_CATALOG_VERSION = "1.0"
FIELD_CATALOG_HASH = stable_json_hash(
    {
        "catalog_version": FIELD_CATALOG_VERSION,
        "model_layer_contract_version": MODEL_LAYER_CONTRACT_VERSION,
        "fields": [
            {"name": name, "tier": _SIGNAL_FIELD_CATALOG[name]} for name in SIGNAL_MODEL_FEATURE_FIELDS
        ],
    }
)


def required_signal_feature_fields() -> frozenset[str]:
    return frozenset(f for f, tier in _SIGNAL_FIELD_CATALOG.items() if tier == "required")


def compare_vector_keys_to_canonical(feature_map: Mapping[str, Any]) -> dict[str, Any]:
    """Explizite Abweichung vom kanonischen Spaltenumfang."""
    keys = set(feature_map.keys()) if feature_map else set()
    missing = sorted(_VECTOR_FIELDS_SET - keys)
    extra = sorted(keys - _VECTOR_FIELDS_SET)
    return {
        "canonical_field_count": len(SIGNAL_MODEL_FEATURE_FIELDS),
        "actual_key_count": len(keys),
        "missing_canonical_fields": missing,
        "extra_fields": extra,
        "exact_key_match": not missing and not extra,
    }


def _leak_value_is_informative(value: Any) -> bool:
    if value is None or value == "":
        return False
    if value is False:
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


def audit_signal_snapshot_row_for_leakage(signal_snapshot: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(signal_snapshot, Mapping):
        return []
    leaked: list[str] = []
    for key in LEAK_PRONE_SIGNAL_SNAPSHOT_KEYS:
        if key not in signal_snapshot:
            continue
        if _leak_value_is_informative(signal_snapshot[key]):
            leaked.append(key)
    return sorted(leaked)


def canonical_model_layer_descriptor(*, include_field_tiers: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "model_layer_contract_version": MODEL_LAYER_CONTRACT_VERSION,
        "upstream": {
            "model_contract_version": MODEL_CONTRACT_VERSION,
            "feature_snapshot_schema_version": FEATURE_SCHEMA_VERSION,
            "feature_snapshot_schema_hash": FEATURE_SCHEMA_HASH,
        },
        "signal_model_feature_vector": {
            "schema_kind": "signal_model_feature_vector",
            "schema_version": SIGNAL_MODEL_FEATURE_SCHEMA_VERSION,
            "schema_hash": SIGNAL_MODEL_FEATURE_SCHEMA_HASH,
            "ordered_field_count": len(SIGNAL_MODEL_FEATURE_FIELDS),
        },
        "field_catalog": {
            "catalog_version": FIELD_CATALOG_VERSION,
            "catalog_hash": FIELD_CATALOG_HASH,
        },
    }
    if include_field_tiers:
        out["field_catalog"]["tiers"] = {f: _SIGNAL_FIELD_CATALOG[f] for f in SIGNAL_MODEL_FEATURE_FIELDS}
    return out
