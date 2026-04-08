from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from learning_engine.config import LearningEngineSettings

logger = logging.getLogger("learning_engine.mlflow")


def log_learning_run(settings: LearningEngineSettings, report: dict[str, Any]) -> None:
    """Optional: MLflow Experiment Tracking (Runs, Params, Metrics, Artifacts)."""
    if not settings.learning_enable_mlflow:
        return
    uri = settings.mlflow_tracking_uri.strip()
    if not uri:
        logger.warning("LEARNING_ENABLE_MLFLOW ohne MLFLOW_TRACKING_URI — skip")
        return
    try:
        import mlflow
    except ImportError:
        logger.warning("mlflow nicht installiert — skip tracking")
        return

    mlflow.set_tracking_uri(uri)
    windows = settings.learning_window_list
    try:
        mlflow.set_experiment("learning_engine_v1")
    except Exception:
        pass
    with mlflow.start_run():
        mlflow.log_params(
            {
                "learning_window_list": windows,
                "learning_promote_pf": settings.learning_promote_pf,
                "learning_retire_pf": settings.learning_retire_pf,
                "learning_max_dd": settings.learning_max_dd,
                "learning_adwin_metric": settings.learning_adwin_metric,
            }
        )
        flat_metrics: dict[str, float] = {}
        for w, block in report.get("windows", {}).items():
            agg = block.get("aggregate_metrics") or {}
            for k, v in agg.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, float) and (v == float("inf") or v != v):
                    continue
                if isinstance(v, (int, float)):
                    flat_metrics[f"{w}_{k}"] = float(v)
        if flat_metrics:
            mlflow.log_metrics(flat_metrics)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(report, tmp, indent=2, default=str)
            tmp_path = Path(tmp.name)
        try:
            mlflow.log_artifact(str(tmp_path), artifact_path="reports")
        finally:
            tmp_path.unlink(missing_ok=True)
