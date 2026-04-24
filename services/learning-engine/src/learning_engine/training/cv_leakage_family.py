"""
CV-Fold-Audit: Symbol-Overlap, Marktfamilie, und zeitliche Purge/Embargo-Invarianten.

Walk-Forward und Purged-KFold nutzen zentrale Split-Bausteine in ``backtest.splits``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from learning_engine.backtest.splits import (
    Range,
    build_purge_embargo_guard_band,
    purged_kfold_embargo_indices,
    range_time_overlap,
    walk_forward_indices,
)
from learning_engine.config import LearningEngineSettings
from learning_engine.training.cv_runner import FoldMetric, folds_to_jsonable
from learning_engine.training.cv_split_policy import (
    make_training_purged_kfold_splits,
    make_training_walk_forward_splits,
)


def verify_temporal_leakage_for_folds(
    ranges: list[Range],
    splits: list[tuple[list[int], list[int]]],
    *,
    purge_ms: int,
    embargo_ms: int,
) -> dict[str, Any]:
    """
    Prueft: Kein Train-``Range`` schneidet das Sperrband
    [test_start - purge, test_end + embargo] pro Fold.
    """
    violations: list[dict[str, Any]] = []
    for fi, (tr_idx, te_idx) in enumerate(splits):
        if not te_idx:
            continue
        t0 = min(ranges[j].start for j in te_idx)
        t1 = max(ranges[j].end for j in te_idx)
        band = build_purge_embargo_guard_band(
            t0, t1, purge_ms=purge_ms, embargo_ms=embargo_ms
        )
        for j in tr_idx:
            if j < 0 or j >= len(ranges):
                continue
            if range_time_overlap(ranges[j], band):
                violations.append(
                    {
                        "fold_index": fi,
                        "train_index": j,
                        "train_range": {"start": ranges[j].start, "end": ranges[j].end},
                        "test_block": {"start": t0, "end": t1},
                    }
                )
    return {
        "ok": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations[:32],
        "purge_ms": purge_ms,
        "embargo_ms": embargo_ms,
    }


def _count_keys(values: list[str], indices: list[int]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for i in indices:
        if i < 0 or i >= len(values):
            continue
        key = values[i] if values[i] else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def fold_symbol_leakage(
    train_idx: list[int], test_idx: list[int], symbols: list[str]
) -> dict[str, Any]:
    tr = {symbols[i] for i in train_idx if i < len(symbols) and symbols[i]}
    te = {symbols[i] for i in test_idx if i < len(symbols) and symbols[i]}
    overlap = sorted(tr & te)
    return {
        "train_symbol_cardinality": len(tr),
        "test_symbol_cardinality": len(te),
        "symbols_in_train_and_test": overlap,
        "strict_symbol_overlap": len(overlap) > 0,
    }


def enrich_cv_folds_with_leakage_and_family(
    folds: list[FoldMetric],
    examples: list[dict[str, Any]],
    splits: list[tuple[list[int], list[int]]],
) -> list[dict[str, Any]]:
    symbols = [str(ex.get("symbol") or "") for ex in examples]
    families = [str(ex.get("market_family") or "unknown") for ex in examples]
    out: list[dict[str, Any]] = []
    for i, fm in enumerate(folds):
        row: dict[str, Any] = {
            "fold_index": fm.fold_index,
            "train_n": fm.train_n,
            "test_n": fm.test_n,
            "skipped_reason": fm.skipped_reason,
        }
        if fm.skipped_reason or i >= len(splits):
            out.append(row)
            continue
        tr_idx, te_idx = splits[i]
        row["symbol_leakage"] = fold_symbol_leakage(tr_idx, te_idx, symbols)
        row["market_family_train_counts"] = _count_keys(families, tr_idx)
        row["market_family_test_counts"] = _count_keys(families, te_idx)
        out.append(row)
    return out


def enrich_with_split_fn(
    folds: list[FoldMetric],
    examples: list[dict[str, Any]],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    split_fn: Callable[[list[Range], int, float], list[tuple[list[int], list[int]]]],
) -> list[dict[str, Any]]:
    splits = split_fn(ranges, k_folds, embargo_pct)
    return enrich_cv_folds_with_leakage_and_family(folds, examples, splits)


_AUDIT_EXTRA_KEYS = frozenset(
    {"symbol_leakage", "market_family_train_counts", "market_family_test_counts"}
)


def merge_audit_fields_into_jsonable_folds(
    jsonable_folds: list[dict[str, Any]],
    fold_audits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(jsonable_folds) != len(fold_audits):
        raise ValueError(
            "CV fold count mismatch: "
            f"metrics folds={len(jsonable_folds)} audit folds={len(fold_audits)}"
        )
    out: list[dict[str, Any]] = []
    for jrow, aud in zip(jsonable_folds, fold_audits, strict=True):
        merged = dict(jrow)
        for k in _AUDIT_EXTRA_KEYS:
            if k in aud:
                merged[k] = aud[k]
        out.append(merged)
    return out


def build_cv_report_with_leakage_family_audit(
    *,
    cv_wf: list[FoldMetric],
    cv_pk: list[FoldMetric],
    examples: list[dict[str, Any]],
    ranges: list[Range],
    k_folds: int,
    embargo_pct: float,
    metric_summary: dict[str, Any],
    settings: LearningEngineSettings | None = None,
) -> dict[str, Any]:
    """Walk-Forward + Purged-KFold JSON, angereichert; mit ``settings`` dieselben Splits wie im Training."""
    wf_json = folds_to_jsonable(cv_wf)
    pk_json = folds_to_jsonable(cv_pk)
    if settings is not None:
        wf_s = make_training_walk_forward_splits(ranges, settings)
        pk_s = make_training_purged_kfold_splits(ranges, settings)
        wf_audit = enrich_cv_folds_with_leakage_and_family(cv_wf, examples, wf_s)
        pk_audit = enrich_cv_folds_with_leakage_and_family(cv_pk, examples, pk_s)
    else:
        wf_audit = enrich_with_split_fn(
            cv_wf, examples, ranges, k_folds, embargo_pct, walk_forward_indices
        )
        pk_audit = enrich_with_split_fn(
            cv_pk, examples, ranges, k_folds, embargo_pct, purged_kfold_embargo_indices
        )
    summary = dict(metric_summary)
    summary["symbol_leakage_walk_forward"] = summarize_symbol_leakage(wf_audit)
    summary["symbol_leakage_purged_kfold_embargo"] = summarize_symbol_leakage(pk_audit)
    return {
        "walk_forward": merge_audit_fields_into_jsonable_folds(wf_json, wf_audit),
        "purged_kfold_embargo": merge_audit_fields_into_jsonable_folds(
            pk_json, pk_audit
        ),
        "summary": summary,
    }


def summarize_symbol_leakage(fold_audits: list[dict[str, Any]]) -> dict[str, Any]:
    leaks = [
        bool(x.get("symbol_leakage", {}).get("strict_symbol_overlap"))
        for x in fold_audits
        if isinstance(x.get("symbol_leakage"), dict)
    ]
    return {
        "folds_with_symbol_overlap": sum(1 for v in leaks if v),
        "folds_audited": len(leaks),
        "note_de": (
            "strict_symbol_overlap=True bedeutet: dieselbe Symbol-ID in Train- und Test-Index "
            "des Folds (bei Multi-Symbol-Pools pruefen, ob zeitliche Trennung ausreicht)."
        ),
    }
