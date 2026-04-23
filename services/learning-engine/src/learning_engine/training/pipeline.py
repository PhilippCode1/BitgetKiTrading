"""
Einheitlicher Trainingspfad fuer CLI und (optional) API — gleiche Trainer, ein Eintrittspunkt.
"""

from __future__ import annotations

from typing import Any

import psycopg

from learning_engine.config import LearningEngineSettings
from learning_engine.meta_models import (
    train_expected_bps_models,
    train_market_regime_classifier,
    train_take_trade_prob_model,
)
from learning_engine.training.specialist_readiness import audit_specialist_training_readiness


def run_training_jobs(
    conn: psycopg.Connection[Any],
    settings: LearningEngineSettings,
    job: str,
    *,
    symbol: str | None,
    promote: bool,
) -> dict[str, Any]:
    """
    job: take-trade | expected-bps | regime | specialists-audit |
    rl-smoke | rl-consensus-ppo | all

    Gibt strukturierte Ergebnisse pro Teiljob zurueck (fuer --summary-out).
    """
    out: dict[str, Any] = {"job": job, "symbol": symbol, "promote": promote, "results": {}}
    if job == "specialists-audit":
        out["results"]["specialists_readiness"] = audit_specialist_training_readiness(
            conn, settings, symbol=symbol
        )
        return out
    if job in ("rl-smoke", "rl-consensus-ppo"):
        from learning_engine.training.rl_train import run_rl_training_jobs

        out["results"][job.replace("-", "_")] = run_rl_training_jobs(
            conn, settings, job=job, symbol=symbol, promote=promote
        )
        return out
    if job in ("take-trade", "all"):
        out["results"]["take_trade_prob"] = train_take_trade_prob_model(
            conn, settings, symbol=symbol, promote=promote
        )
    if job in ("expected-bps", "all"):
        out["results"]["expected_bps"] = train_expected_bps_models(
            conn, settings, symbol=symbol, promote=promote
        )
    if job in ("regime", "all"):
        out["results"]["regime_classifier"] = train_market_regime_classifier(
            conn, settings, symbol=symbol, promote=promote
        )
    return out
