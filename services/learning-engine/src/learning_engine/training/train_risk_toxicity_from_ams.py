"""
Trainiert einen leichten RandomForest auf AMS-/toxic-batch Antworten (Order-Flow-Toxizitaet).

Speichert joblib nach ``RISK_TOXICITY_CLASSIFIER_MODEL_PATH`` (LearningEngineSettings).

Aufruf:
  CONFIG_ENV_FILE=.env.local python -m learning_engine.training.train_risk_toxicity_from_ams
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

import httpx
import numpy as np


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


def main() -> int:
    _ensure_paths()
    from config.bootstrap import bootstrap_from_settings
    from learning_engine.config import LearningEngineSettings
    from learning_engine.stress_test.features import features_from_ams_moments

    settings = LearningEngineSettings()
    bootstrap_from_settings("learning-engine", settings)
    out_path = (settings.risk_toxicity_classifier_model_path or "").strip()
    if not out_path:
        print("RISK_TOXICITY_CLASSIFIER_MODEL_PATH fehlt", file=sys.stderr)
        return 2
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    base = (settings.adversarial_engine_base_url or "").strip().rstrip("/")
    url = f"{base}/ams/v1/toxic-batch"
    rng = random.Random(42)
    xs: list[np.ndarray] = []
    ys: list[int] = []

    headers: dict[str, str] = {}
    key = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if key:
        from shared_py.service_auth import INTERNAL_SERVICE_HEADER

        headers[INTERNAL_SERVICE_HEADER] = key

    with httpx.Client(timeout=120.0) as client:
        for _ in range(800):
            tox = rng.uniform(0.2, 1.0)
            body = {
                "symbol": "BTCUSDT",
                "seq_len": 160,
                "toxicity_0_1": tox,
                "batch": 1,
                "return_arrow": False,
                "seed": rng.randint(1, 2_000_000_000),
            }
            r = client.post(url, json=body, headers=headers)
            r.raise_for_status()
            j = r.json()
            moments = j.get("moments") if isinstance(j, dict) else {}
            if not isinstance(moments, dict):
                moments = {}
            x = features_from_ams_moments(moments, float(tox))
            xs.append(x)
            ys.append(1 if tox >= 0.72 else 0)

    X = np.stack(xs, axis=0)
    y = np.asarray(ys, dtype=np.int64)
    from sklearn.ensemble import RandomForestClassifier

    clf = RandomForestClassifier(
        n_estimators=48,
        max_depth=8,
        random_state=42,
        class_weight="balanced",
    )
    clf.fit(X, y)
    import joblib

    joblib.dump(clf, out_path)
    print(f"ok: saved RandomForest to {out_path} rows={X.shape[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
