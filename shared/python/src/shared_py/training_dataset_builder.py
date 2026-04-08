"""
Reproduzierbarer Dataset-Builder fuer Learning-Engine: Rohzeilen -> Trainingsbeispiele.

Zeitbezug: primary_tf.computed_ts_ms vs decision_ts_ms.
Schutz: Target-/Modell-Leakage in signal_snapshot, Freshness-Gate, Required-NaN-Gate,
Schema-Drift-Zaehlung.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from shared_py.model_contracts import extract_primary_feature_snapshot, stable_json_hash
from shared_py.model_layer_contract import (
    audit_signal_snapshot_row_for_leakage,
    compare_vector_keys_to_canonical,
    required_signal_feature_fields,
)
from shared_py.take_trade_model import (
    TAKE_TRADE_FEATURE_FIELDS,
    build_take_trade_feature_vector_from_evaluation,
)


@dataclass(frozen=True)
class TakeTradeDatasetBuildConfig:
    """Konfiguration fuer Hashing und Gates (explizit im Trainings-Manifest festhalten)."""

    max_feature_age_ms: int = 3_600_000
    future_feature_slack_ms: int = 300_000
    drop_on_signal_leak_keys: bool = True
    drop_on_missing_feature_ts: bool = True
    drop_on_stale_features: bool = True
    drop_on_future_feature_ts: bool = True
    drop_on_required_nan: bool = True


def take_trade_dataset_config_fingerprint(cfg: TakeTradeDatasetBuildConfig) -> str:
    return stable_json_hash(
        {
            "kind": "take_trade_dataset_build_config",
            "max_feature_age_ms": cfg.max_feature_age_ms,
            "future_feature_slack_ms": cfg.future_feature_slack_ms,
            "drop_on_signal_leak_keys": cfg.drop_on_signal_leak_keys,
            "drop_on_missing_feature_ts": cfg.drop_on_missing_feature_ts,
            "drop_on_stale_features": cfg.drop_on_stale_features,
            "drop_on_future_feature_ts": cfg.drop_on_future_feature_ts,
            "drop_on_required_nan": cfg.drop_on_required_nan,
        }
    )


def _coerce_int_ms(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def feature_snapshot_asof_ms(row: Mapping[str, Any]) -> int | None:
    raw = row.get("feature_snapshot_json")
    if not isinstance(raw, Mapping):
        return None
    primary = extract_primary_feature_snapshot(raw)
    if not isinstance(primary, Mapping):
        return None
    return _coerce_int_ms(primary.get("computed_ts_ms"))


@dataclass
class TakeTradeDatasetBuildReport:
    kept_count: int = 0
    dropped: dict[str, int] = field(default_factory=dict)
    schema_drift_samples: list[dict[str, Any]] = field(default_factory=list)
    config_fingerprint: str = ""

    def record_drop(self, reason: str) -> None:
        self.dropped[reason] = self.dropped.get(reason, 0) + 1


def _finite_scalar(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return True
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f)


def training_row_metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    """Symbol, Marktfamilie und Fehler-Labels fuer CV-Audit / Spezialisten-Splits (keine Feature-Spalten)."""
    sym = str(row.get("symbol") or "").strip().upper()
    market_family: str | None = None
    sig = row.get("signal_snapshot_json")
    if isinstance(sig, Mapping):
        inst = sig.get("instrument")
        if isinstance(inst, Mapping):
            mf = inst.get("market_family")
            if mf is not None and str(mf).strip():
                market_family = str(mf).strip().lower()
    if market_family is None:
        feat = row.get("feature_snapshot_json")
        if isinstance(feat, Mapping):
            primary = extract_primary_feature_snapshot(feat)
            if isinstance(primary, Mapping):
                mf2 = primary.get("market_family")
                if mf2 is not None and str(mf2).strip():
                    market_family = str(mf2).strip().lower()
    err_raw = row.get("error_labels_json")
    labels: list[str] = []
    if isinstance(err_raw, list):
        labels = [str(x) for x in err_raw]
    elif isinstance(err_raw, str) and err_raw.strip():
        try:
            parsed = json.loads(err_raw)
            if isinstance(parsed, list):
                labels = [str(x) for x in parsed]
        except json.JSONDecodeError:
            labels = []
    return {
        "symbol": sym,
        "market_family": market_family or "unknown",
        "error_labels": labels,
    }


def _example_from_evaluation_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    target = row.get("take_trade_label")
    if target is None:
        return None
    features = build_take_trade_feature_vector_from_evaluation(dict(row))
    if not features:
        return None
    closed_raw = row.get("closed_ts_ms")
    closed_ts_ms = int(closed_raw) if closed_raw is not None else None
    meta = training_row_metadata(row)
    return {
        "paper_trade_id": str(row.get("paper_trade_id") or ""),
        "decision_ts_ms": int(row.get("decision_ts_ms") or 0),
        "closed_ts_ms": closed_ts_ms,
        "market_regime": str(row.get("market_regime") or "unknown"),
        "symbol": meta["symbol"],
        "market_family": meta["market_family"],
        "error_labels": meta["error_labels"],
        "features": features,
        "target": 1 if bool(target) else 0,
    }


def build_take_trade_training_dataset(
    rows: list[dict[str, Any]],
    config: TakeTradeDatasetBuildConfig,
    *,
    row_to_example: Callable[[Mapping[str, Any]], dict[str, Any] | None] | None = None,
    max_schema_drift_samples: int = 5,
) -> tuple[list[dict[str, Any]], TakeTradeDatasetBuildReport]:
    """
    Filtert und validiert Zeilen aus learn.trade_evaluations (oder gleiches Layout).

    row_to_example: optionaler Hook fuer Tests; Standard baut den Signal+Feature-Vektor.
    """
    to_example = row_to_example or _example_from_evaluation_row
    report = TakeTradeDatasetBuildReport(config_fingerprint=take_trade_dataset_config_fingerprint(config))
    kept: list[dict[str, Any]] = []
    required_fields = required_signal_feature_fields()
    drift_logged = 0

    for row in rows:
        sig = row.get("signal_snapshot_json")
        leak_keys = audit_signal_snapshot_row_for_leakage(
            sig if isinstance(sig, Mapping) else None
        )
        if leak_keys and config.drop_on_signal_leak_keys:
            report.record_drop("signal_snapshot_leak_keys")
            continue

        example = to_example(row)
        if example is None:
            report.record_drop("missing_target_or_empty_features")
            continue

        drift = compare_vector_keys_to_canonical(example["features"])
        if not drift["exact_key_match"] and drift_logged < max_schema_drift_samples:
            report.schema_drift_samples.append({"paper_trade_id": example["paper_trade_id"], **drift})
            drift_logged += 1
        if not drift["exact_key_match"]:
            report.record_drop("schema_key_mismatch")
            continue

        decision_ts = int(example["decision_ts_ms"])
        asof = feature_snapshot_asof_ms(row)

        if asof is None:
            if config.drop_on_missing_feature_ts:
                report.record_drop("missing_feature_computed_ts_ms")
                continue
        else:
            if config.drop_on_future_feature_ts and asof > decision_ts + config.future_feature_slack_ms:
                report.record_drop("feature_ts_after_decision_leak")
                continue
            if config.drop_on_stale_features and decision_ts - asof > config.max_feature_age_ms:
                report.record_drop("stale_features")
                continue

        if config.drop_on_required_nan:
            feats = example["features"]
            bad = any(not _finite_scalar(feats.get(f)) for f in required_fields)
            if bad:
                report.record_drop("required_feature_nan")
                continue

        kept.append(example)
        report.kept_count += 1

    return kept, report


def training_feature_matrix(
    examples: Sequence[Mapping[str, Any]],
) -> tuple[list[list[float]], list[int]]:
    X = [[float(example["features"][name]) for name in TAKE_TRADE_FEATURE_FIELDS] for example in examples]
    y = [int(example["target"]) for example in examples]
    return X, y
