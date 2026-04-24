"""
Drift-Retrain take_trade_prob: Challenger PENDING_EVAL, kein Promote.
CLI: ``python -m learning_engine.drift.drift_retrain_subprocess``.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID, uuid4

import psycopg
from shared_py.take_trade_model import TAKE_TRADE_MODEL_NAME, TAKE_TRADE_TARGET_FIELD

from learning_engine.config import LearningEngineSettings
from learning_engine.storage import repo_model_runs
from learning_engine.storage.connection import db_connect
from learning_engine.storage.repo_model_registry_v2 import upsert_registry_slot

log = logging.getLogger("learning_engine.drift_retrain")

_METADATA_ORIGIN = "drift_mse_retrain"
_METADATA_ORIGIN_SMOKE = "drift_mse_retrain_smoke"


def _min_decision_ts_ms(*, window_days: int) -> int:
    now = int(time.time() * 1000)
    return now - int(window_days) * 24 * 3600 * 1000


def run_drift_retrain(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    *,
    window_days: int | None = None,
) -> dict[str, Any]:
    """
    take_trade-Training mit min_decision_ts, ``promote=False``; Registry Challenger.
    Smoke: nur model_runs + registry (kein Sklearn).
    """
    wd = int(
        window_days
        if window_days is not None
        else settings.learning_drift_retrain_window_days
    )
    min_ts = _min_decision_ts_ms(window_days=wd)
    extras: dict[str, Any] = {
        "lifecycle_status": "PENDING_EVAL",
        "origin": _METADATA_ORIGIN_SMOKE
        if settings.learning_drift_retrain_smoke
        else _METADATA_ORIGIN,
        "min_decision_ts_ms": min_ts,
        "window_days": wd,
    }
    if settings.learning_drift_retrain_smoke:
        return _retrain_smoke(
            conn,
            min_decision_ts_ms=min_ts,
            metadata_extras=extras,
        )
    from learning_engine.meta_models.take_trade_prob import train_take_trade_prob_model

    out = train_take_trade_prob_model(
        conn,
        settings,
        promote=False,
        min_decision_ts_ms=min_ts,
        metadata_extras=extras,
    )
    upsert_registry_slot(
        conn,
        model_name=TAKE_TRADE_MODEL_NAME,
        role="challenger",
        run_id=UUID(str(out["run_id"])),
        calibration_status="PENDING_EVAL",
        notes="MSE-Drift Retrain (Challenger, kein Autopromote)",
    )
    log.info(
        "drift retrain vollstaendig (challenger PENDING_EVAL)",
        extra={"run_id": out["run_id"]},
    )
    return {**out, "registry_role": "challenger"}


def _retrain_smoke(
    conn: psycopg.Connection[Any],
    *,
    min_decision_ts_ms: int,
    metadata_extras: dict[str, Any],
) -> dict[str, Any]:
    run_id = uuid4()
    meta = {**metadata_extras, "smoke": True}
    repo_model_runs.insert_model_run(
        conn,
        run_id=run_id,
        model_name=TAKE_TRADE_MODEL_NAME,
        version="drift-smoke",
        dataset_hash="drift-smoke",
        metrics_json={"smoke": True},
        promoted_bool=False,
        artifact_path=None,
        target_name=TAKE_TRADE_TARGET_FIELD,
        output_field="take_trade_prob",
        calibration_method="none",
        metadata_json=meta,
    )
    upsert_registry_slot(
        conn,
        model_name=TAKE_TRADE_MODEL_NAME,
        role="challenger",
        run_id=run_id,
        calibration_status="PENDING_EVAL",
        notes="MSE-Drift Retrain Smoke",
    )
    log.info(
        "drift retrain smoke (challenger PENDING_EVAL)", extra={"run_id": str(run_id)}
    )
    return {
        "run_id": str(run_id),
        "smoke": True,
        "min_decision_ts_ms": min_decision_ts_ms,
        "registry_role": "challenger",
    }


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    s = LearningEngineSettings()
    with db_connect(s.database_url) as conn:
        with conn.transaction():
            run_drift_retrain(conn, s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
