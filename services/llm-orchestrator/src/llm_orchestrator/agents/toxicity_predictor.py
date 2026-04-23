"""Leichtgewichtiger sklearn-RandomForest (joblib) fuer Order-Flow-Toxizitaet."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("llm_orchestrator.agents.toxicity_predictor")


class ToxicityClassifier:
    def __init__(self, model_path: str | None) -> None:
        self._path = (model_path or "").strip()
        self._clf: Any | None = None
        if self._path and Path(self._path).is_file():
            try:
                import joblib

                self._clf = joblib.load(self._path)
                logger.info("Toxizitaets-Klassifikator geladen: %s", self._path)
            except Exception as exc:
                logger.warning("Toxizitaets-Modell nicht ladbar: %s", exc)
                self._clf = None
        elif self._path:
            logger.debug("Toxizitaets-Modell-Pfad gesetzt aber Datei fehlt: %s", self._path)

    def predict_trap_proba(self, x: np.ndarray) -> float | None:
        if self._clf is None:
            return None
        try:
            if hasattr(self._clf, "predict_proba"):
                p = np.asarray(self._clf.predict_proba(x.reshape(1, -1)))[0, 1]
                return float(p)
            pred = int(self._clf.predict(x.reshape(1, -1))[0])
            return 1.0 if pred == 1 else 0.0
        except Exception as exc:
            logger.debug("toxicity predict failed: %s", exc)
            return None
