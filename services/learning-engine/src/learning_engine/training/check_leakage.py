"""
DoD (Prompt 47): Purge/Embargo Walk-Forward, zeitliche Train/Test-Trennung pruefen.

``python -m learning_engine.training --check-leakage``
"""

from __future__ import annotations

import json
import os

from learning_engine.backtest.splits import Range
from learning_engine.config import LearningEngineSettings
from learning_engine.training.cv_leakage_family import verify_temporal_leakage_for_folds
from learning_engine.training.cv_split_policy import (
    make_training_walk_forward_splits,
    train_cv_embargo_ms_effective,
)

# Beispiel: 2h Kerzen-Abstand (kann per TRAIN_CV_PURGE_MS in Settings ueberschrieben werden)
DOD_EXAMPLE_PURGE_MS = 2 * 3600 * 1000


def _ensure_minimal_env_for_settings() -> None:
    """Nur fuer isolierten --check-leakage-Lauf (keine echten Verbindungen)."""
    if not (os.getenv("DATABASE_URL") or "").strip():
        os.environ["DATABASE_URL"] = "postgresql://u:p@127.0.0.1:5432/dummy"
    if not (os.getenv("REDIS_URL") or "").strip():
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
    if (os.getenv("LIVE_TRADE_ENABLE") or "").strip().lower() in ("1", "true", "yes"):
        if (os.getenv("EXECUTION_MODE") or "").strip().lower() != "live":
            os.environ["LIVE_TRADE_ENABLE"] = "false"
    if not (os.getenv("EXECUTION_MODE") or "").strip():
        os.environ["EXECUTION_MODE"] = "paper"


def run_check_leakage(*, purge_ms: int | None = None) -> dict:
    """
    Synthetische 2h-Abstaende, purged walk-forward mit Settings, dann
    `verify_temporal_leakage_for_folds` (kein Train-Index im Purge+Embargo-Band).
    """
    _ensure_minimal_env_for_settings()
    s = LearningEngineSettings()
    if purge_ms is not None:
        pm = int(purge_ms)
    else:
        pm = int(s.train_cv_purge_ms or DOD_EXAMPLE_PURGE_MS)
    s.train_cv_purge_ms = pm
    s.train_cv_kfolds = 5
    s.train_cv_min_initial_train_pct = 0.1
    s.train_cv_exclude_prior_test = True
    s.train_cv_embargo_pct = 0.05
    s.train_cv_embargo_time_ms = 0
    base = 1_700_000_000_000
    step = max(pm, 60_000)
    n = 100
    ranges = [Range(base + i * step, base + i * step + 60_000) for i in range(n)]
    spl = make_training_walk_forward_splits(ranges, s)
    em = train_cv_embargo_ms_effective(ranges, s)
    return verify_temporal_leakage_for_folds(ranges, spl, purge_ms=pm, embargo_ms=em)


def main() -> int:
    rep = run_check_leakage()
    print(json.dumps(rep, indent=2, default=str))
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
