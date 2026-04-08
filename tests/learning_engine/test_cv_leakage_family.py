from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARNING_SRC = ROOT / "services" / "learning-engine" / "src"
if LEARNING_SRC.is_dir() and str(LEARNING_SRC) not in sys.path:
    sys.path.insert(0, str(LEARNING_SRC))

from learning_engine.backtest.splits import Range
from learning_engine.training.cv_leakage_family import (
    build_cv_report_with_leakage_family_audit,
    fold_symbol_leakage,
    merge_audit_fields_into_jsonable_folds,
)
from learning_engine.training.cv_runner import FoldMetric


def test_fold_symbol_leakage_strict_overlap() -> None:
    symbols = ["AAA", "AAA", "BBB"]
    leak = fold_symbol_leakage([0, 1], [0, 2], symbols)
    assert leak["strict_symbol_overlap"] is True
    assert "AAA" in leak["symbols_in_train_and_test"]


def test_merge_audit_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="fold count mismatch"):
        merge_audit_fields_into_jsonable_folds([{"fold_index": 0}], [{}, {}])


def test_build_cv_report_enriches_folds() -> None:
    n = 20
    k = 5
    examples = [
        {"symbol": f"S{i % 3}", "market_family": "futures" if i % 2 == 0 else "spot"}
        for i in range(n)
    ]
    ranges = [Range(1_000_000 + i * 10_000, 1_000_000 + i * 10_000 + 5_000) for i in range(n)]
    cv_wf = [
        FoldMetric(
            fold_index=i,
            train_n=12,
            test_n=4,
            metrics={"roc_auc": 0.66},
            skipped_reason=None,
        )
        for i in range(k)
    ]
    cv_pk = [
        FoldMetric(
            fold_index=i,
            train_n=12,
            test_n=4,
            metrics={"roc_auc": 0.61},
            skipped_reason=None,
        )
        for i in range(k)
    ]
    rep = build_cv_report_with_leakage_family_audit(
        cv_wf=cv_wf,
        cv_pk=cv_pk,
        examples=examples,
        ranges=ranges,
        k_folds=k,
        embargo_pct=0.05,
        metric_summary={"walk_forward_mean_roc_auc": 0.65},
    )
    assert "walk_forward" in rep and "purged_kfold_embargo" in rep
    assert len(rep["walk_forward"]) == k
    first = rep["walk_forward"][0]
    assert "symbol_leakage" in first
    assert "market_family_train_counts" in first
    assert "symbol_leakage_walk_forward" in rep["summary"]
    assert rep["summary"]["symbol_leakage_walk_forward"]["folds_audited"] == k
