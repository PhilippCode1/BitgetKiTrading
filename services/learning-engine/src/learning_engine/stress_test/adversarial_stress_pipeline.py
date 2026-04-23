"""
Stress-Test-Pipeline: N AMS-Aufrufe, Bewertung via trainiertem Toxizitaets-Klassifikator.

Champion-Promotion: ``resilience_score_0_100`` muss i.d.R. >= 90 (LearningEngineSettings).
"""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from learning_engine.config import LearningEngineSettings
from learning_engine.stress_test.features import features_from_ams_moments
from learning_engine.stress_test.schemas import AdversarialAttackOutcomeV1, AdversarialStressRunResultV1


def _load_classifier(path: str | None) -> Any | None:
    if not path or not Path(path).is_file():
        return None
    try:
        import joblib

        return joblib.load(path)
    except Exception:
        return None


def run_adversarial_stress_suite(
    settings: LearningEngineSettings,
    *,
    attack_count: int | None = None,
    trap_toxicity_threshold: float | None = None,
    min_resilience: float | None = None,
    rng: random.Random | None = None,
) -> AdversarialStressRunResultV1:
    """
    Fuehrt ``attack_count`` POSTs gegen adversarial-engine aus und wertet Trap-Erkennung.

    Deflected (pro Angriff): bei ``high_risk`` muss der Klassifikator Trap-Wahrscheinlichkeit >= 0.5 liefern.
    """
    r = rng or random.Random()
    n = int(attack_count or settings.adversarial_stress_attack_count)
    thr = float(trap_toxicity_threshold or settings.adversarial_stress_trap_toxicity_threshold)
    min_ok = float(min_resilience or settings.model_promotion_min_resilience_score_0_100)
    base = (settings.adversarial_engine_base_url or "").strip().rstrip("/")
    clf = _load_classifier((settings.risk_toxicity_classifier_model_path or "").strip() or None)

    url = f"{base}/ams/v1/toxic-batch"
    headers: dict[str, str] = {}
    key = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if key:
        from shared_py.service_auth import INTERNAL_SERVICE_HEADER

        headers[INTERNAL_SERVICE_HEADER] = key

    outcomes: list[AdversarialAttackOutcomeV1] = []
    high_risk = 0
    deflected = 0

    with httpx.Client(timeout=120.0) as client:
        for i in range(n):
            tox = r.uniform(0.35, 1.0)
            body = {
                "symbol": "BTCUSDT",
                "seq_len": 160,
                "toxicity_0_1": tox,
                "batch": 1,
                "return_arrow": False,
                "seed": r.randint(1, 2_000_000_000),
            }
            resp = client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            j = resp.json()
            moments = j.get("moments") if isinstance(j, dict) else {}
            if not isinstance(moments, dict):
                moments = {}
            is_high = tox >= thr
            trap_p: float | None = None
            blocked = False
            if clf is not None:
                x = features_from_ams_moments(moments, tox).reshape(1, -1)
                try:
                    if hasattr(clf, "predict_proba"):
                        trap_p = float(np.asarray(clf.predict_proba(x))[0, 1])
                        blocked = trap_p >= 0.5
                    else:
                        pr = clf.predict(x)
                        blocked = int(pr[0]) == 1
                        trap_p = 1.0 if blocked else 0.0
                except Exception:
                    blocked = False
            else:
                # Heuristik ohne Modell: Kurtosis-Spitze als Proxy
                lr = moments.get("log_return") or {}
                k = float(lr.get("kurtosis_excess") or 0.0)
                trap_p = float(min(1.0, max(0.0, 0.25 * k + tox * 0.5)))
                blocked = trap_p >= 0.55 and is_high

            if is_high:
                high_risk += 1
                if blocked:
                    deflected += 1

            if len(outcomes) < 24:
                outcomes.append(
                    AdversarialAttackOutcomeV1(
                        attack_index=i,
                        toxicity_0_1=float(tox),
                        high_risk=is_high,
                        deflected=bool(blocked) if is_high else True,
                        trap_score=trap_p,
                    )
                )

    score = 100.0 * float(deflected) / float(high_risk) if high_risk > 0 else 0.0
    min_high = max(120, n // 5)
    passed = bool(score >= min_ok and high_risk >= min_high)

    return AdversarialStressRunResultV1(
        attacks_total=n,
        attacks_high_risk=high_risk,
        attacks_deflected=deflected,
        resilience_score_0_100=round(score, 4),
        min_resilience_required_0_100=min_ok,
        passed=bool(passed),
        classifier_path=(settings.risk_toxicity_classifier_model_path or None),
        adversarial_engine_base_url=base or None,
        sample_outcomes=outcomes,
        details={
            "trap_toxicity_threshold": thr,
            "evaluated_at_ts_ms": int(time.time() * 1000),
            "classifier_loaded": clf is not None,
            "min_high_risk_required": min_high,
            "high_risk_ok": high_risk >= min_high,
        },
    )


def resilience_to_dashboard_dict(result: AdversarialStressRunResultV1) -> dict[str, Any]:
    """JSON fuer Dashboard / API (validierbar gegen ``resilience_score.schema.json``)."""
    return {
        "schema_version": "resilience_score_v1",
        "resilience_score_0_100": float(result.resilience_score_0_100),
        "attacks_total": int(result.attacks_total),
        "attacks_deflected": int(result.attacks_deflected),
        "attack_budget": int(result.attacks_total),
        "toxicity_threshold": float(result.details.get("trap_toxicity_threshold", 0.0)),
        "classifier_model_path": result.classifier_path,
        "mode": "simulation",
        "evaluated_at_ts_ms": int(result.details.get("evaluated_at_ts_ms") or 0),
        "details": {
            "passed": result.passed,
            "min_required": float(result.min_resilience_required_0_100),
            "attacks_high_risk": int(result.attacks_high_risk),
            "stress_schema": result.schema_version,
        },
    }
