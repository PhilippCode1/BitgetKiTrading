"""
TSFM (Deep / Foundation-Model-Pfade): zwingend dieselbe purged/embargo CV-Logik
wie die Learning-Engine-Trainer (kein eigenes K-Fold ohne Purge).
"""

from __future__ import annotations

from typing import Any

from learning_engine.config import LearningEngineSettings
from learning_engine.training.check_leakage import (
    DOD_EXAMPLE_PURGE_MS,
    run_check_leakage,
)


def run_tsfm_purged_cv_compliance(settings: LearningEngineSettings) -> dict[str, Any]:
    """
    Policy-Check: TSFM-relevante Pfade sollen `make_training_walk_forward_splits` / Settings
    spiegeln. Fuehrt die DoD-``run_check_leakage``-Baseline mit 2h-Purge mit ein.
    """
    pm = int(settings.train_cv_purge_ms or DOD_EXAMPLE_PURGE_MS)
    return {
        "tsfm_purged_walk_forward_required": True,
        "split_policy": {
            "train_cv_purge_ms": int(settings.train_cv_purge_ms),
            "train_cv_embargo_time_ms": int(settings.train_cv_embargo_time_ms),
            "train_cv_embargo_pct": float(settings.train_cv_embargo_pct),
            "train_cv_min_initial_train_pct": float(
                settings.train_cv_min_initial_train_pct
            ),
            "train_cv_exclude_prior_test": bool(settings.train_cv_exclude_prior_test),
        },
        "dod_check_leakage_2h": run_check_leakage(purge_ms=pm),
    }
