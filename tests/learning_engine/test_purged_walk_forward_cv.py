from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LEARN = ROOT / "services" / "learning-engine" / "src"
SHARED = ROOT / "shared" / "python" / "src"
for p in (LEARN, SHARED):
    s = str(p)
    if p.is_dir() and s not in sys.path:
        sys.path.insert(0, s)

os.environ.setdefault("DATABASE_URL", "postgresql://u:p@127.0.0.1:5432/t")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")

from learning_engine.backtest.splits import Range, purged_walk_forward_indices, walk_forward_indices
from learning_engine.config import LearningEngineSettings
from learning_engine.training.check_leakage import run_check_leakage
from learning_engine.training.cv_leakage_family import verify_temporal_leakage_for_folds
from learning_engine.training.cv_split_policy import (
    make_training_walk_forward_splits,
    train_cv_embargo_ms_effective,
)


def test_purged_walk_forward_verify_always_passes() -> None:
    twoh = 2 * 3600 * 1000
    n = 80
    # 1h Stufen, 1min Label-Span; Purge 2h verlangt lueckenhalt zu Test
    r = [Range(1_000_000_000_000 + i * 3_600_000, 1_000_000_000_000 + i * 3_600_000 + 60_000) for i in range(n)]
    s = LearningEngineSettings()
    s.train_cv_purge_ms = twoh
    s.train_cv_kfolds = 5
    s.train_cv_min_initial_train_pct = 0.1
    s.train_cv_exclude_prior_test = True
    s.train_cv_embargo_time_ms = 0
    s.train_cv_embargo_pct = 0.05
    spl = make_training_walk_forward_splits(r, s)
    em = train_cv_embargo_ms_effective(r, s)
    v = verify_temporal_leakage_for_folds(
        r, spl, purge_ms=int(s.train_cv_purge_ms), embargo_ms=em
    )
    assert v["ok"] is True, v
    assert v["violation_count"] == 0


def test_run_check_leakage_dod() -> None:
    rep = run_check_leakage()
    assert rep.get("ok") is True, rep


def test_purged_vs_walk_forward_same_test_folds() -> None:
    r = [Range(i * 10, i * 10 + 5) for i in range(15)]
    o = walk_forward_indices(r, k=3, embargo_pct=0.0)
    p = purged_walk_forward_indices(
        r, 3, purge_ms=0, embargo_ms=0, min_initial_train=0, exclude_prior_test=True
    )
    assert len(o) == len(p) == 3
    for (_, te_wf), (_, te_p) in zip(o, p, strict=True):
        assert te_wf == te_p
