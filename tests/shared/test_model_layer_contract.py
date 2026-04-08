from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHARED_SRC = ROOT / "shared" / "python" / "src"
if SHARED_SRC.is_dir() and str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from shared_py.model_layer_contract import (
    FIELD_CATALOG_HASH,
    FIELD_CATALOG_VERSION,
    MODEL_LAYER_CONTRACT_VERSION,
    audit_signal_snapshot_row_for_leakage,
    build_signal_field_catalog,
    canonical_model_layer_descriptor,
    compare_vector_keys_to_canonical,
)
from shared_py.take_trade_model import (
    SIGNAL_MODEL_FEATURE_FIELDS,
    build_signal_model_feature_vector,
)


def test_field_catalog_covers_all_vector_fields() -> None:
    catalog = build_signal_field_catalog()
    assert set(catalog) == set(SIGNAL_MODEL_FEATURE_FIELDS)
    assert FIELD_CATALOG_VERSION == "1.0"
    assert len(FIELD_CATALOG_HASH) == 64


def test_canonical_descriptor_links_upstream_hashes() -> None:
    desc = canonical_model_layer_descriptor(include_field_tiers=False)
    assert desc["model_layer_contract_version"] == MODEL_LAYER_CONTRACT_VERSION
    assert desc["upstream"]["feature_snapshot_schema_hash"]
    assert desc["signal_model_feature_vector"]["schema_hash"]
    assert desc["field_catalog"]["catalog_hash"] == FIELD_CATALOG_HASH


def test_compare_vector_keys_detects_drift() -> None:
    vec = build_signal_model_feature_vector(signal_row=None, feature_snapshot=None)
    drift = compare_vector_keys_to_canonical(vec)
    assert drift["exact_key_match"]
    vec2 = dict(vec)
    del vec2[next(iter(vec2))]
    drift2 = compare_vector_keys_to_canonical(vec2)
    assert not drift2["exact_key_match"]
    assert drift2["missing_canonical_fields"]


def test_audit_leak_ignores_empty_and_false_sentinels() -> None:
    assert (
        audit_signal_snapshot_row_for_leakage(
            {
                "take_trade_prob": None,
                "model_ood_alert": False,
                "target_projection_models_json": [],
            }
        )
        == []
    )
    assert audit_signal_snapshot_row_for_leakage({"take_trade_prob": 0.71}) == [
        "take_trade_prob"
    ]
