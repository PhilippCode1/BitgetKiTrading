"""
Trainings-CV: Purge/Embargo Walk-Forward + Purged-KFold aus ``LearningEngineSettings``.

Kein Import von ``cv_runner`` (verhindert Zyklen mit cv_leakage_family).
"""

from __future__ import annotations

from learning_engine.backtest.splits import (
    Range,
    purged_kfold_embargo_indices,
    purged_walk_forward_indices,
)
from learning_engine.config import LearningEngineSettings


def train_cv_embargo_ms_effective(
    ranges: list[Range], settings: LearningEngineSettings
) -> int:
    n = len(ranges)
    total = max(1, ranges[-1].end - ranges[0].start) if n else 1
    if int(settings.train_cv_embargo_time_ms or 0) > 0:
        return int(settings.train_cv_embargo_time_ms)
    return int(round(float(total) * float(settings.train_cv_embargo_pct)))


def make_training_walk_forward_splits(
    ranges: list[Range], settings: LearningEngineSettings
) -> list[tuple[list[int], list[int]]]:
    n = len(ranges)
    em = train_cv_embargo_ms_effective(ranges, settings)
    min_init = int(n * float(settings.train_cv_min_initial_train_pct))
    return purged_walk_forward_indices(
        ranges,
        int(settings.train_cv_kfolds),
        purge_ms=int(settings.train_cv_purge_ms),
        embargo_ms=em,
        min_initial_train=min_init,
        exclude_prior_test=bool(settings.train_cv_exclude_prior_test),
    )


def make_training_purged_kfold_splits(
    ranges: list[Range], settings: LearningEngineSettings
) -> list[tuple[list[int], list[int]]]:
    em_time: int | None
    if int(settings.train_cv_embargo_time_ms or 0) > 0:
        em_time = int(settings.train_cv_embargo_time_ms)
    else:
        em_time = None
    return purged_kfold_embargo_indices(
        ranges,
        int(settings.train_cv_kfolds),
        float(settings.train_cv_embargo_pct),
        purge_ms=int(settings.train_cv_purge_ms),
        embargo_time_ms=em_time,
    )
