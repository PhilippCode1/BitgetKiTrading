from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from learning_engine.config import LearningEngineSettings
from learning_engine.meta_models import (
    train_expected_bps_models,
    train_market_regime_classifier,
    train_take_trade_prob_model,
)
from learning_engine.storage import repo_model_runs
from learning_engine.storage.connection import db_connect
from learning_engine.training.specialist_readiness import audit_specialist_training_readiness
from shared_py.take_trade_model import BPS_REGRESSION_MODEL_NAMES, MARKET_REGIME_CLASSIFIER_MODEL_NAME


def build_models_router(settings: LearningEngineSettings) -> APIRouter:
    r = APIRouter(tags=["learning"])

    @r.get("/learning/models/take-trade/latest")
    def latest() -> dict[str, Any]:
        with db_connect(settings.database_url) as conn:
            row = repo_model_runs.get_latest_model_run(
                conn,
                model_name="take_trade_prob",
                promoted_only=True,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="kein promoted take_trade_prob Modell")
        return {"status": "ok", "model": repo_model_runs.jsonable_row(row)}

    @r.get("/learning/models/take-trade/runs")
    def list_runs(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        with db_connect(settings.database_url) as conn:
            rows = repo_model_runs.list_model_runs(
                conn,
                model_name="take_trade_prob",
                limit=limit,
            )
        return {
            "status": "ok",
            "count": len(rows),
            "items": [repo_model_runs.jsonable_row(row) for row in rows],
        }

    @r.post("/learning/models/take-trade/train-now")
    def train_now(symbol: str | None = None, promote: bool = True) -> dict[str, Any]:
        try:
            with db_connect(settings.database_url) as conn:
                with conn.transaction():
                    report = train_take_trade_prob_model(
                        conn,
                        settings,
                        symbol=symbol,
                        promote=promote,
                    )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "report": report}

    @r.get("/learning/models/expected-bps/latest")
    def latest_expected_bps() -> dict[str, Any]:
        items: dict[str, Any] = {}
        with db_connect(settings.database_url) as conn:
            for model_name in BPS_REGRESSION_MODEL_NAMES:
                row = repo_model_runs.get_latest_model_run(
                    conn,
                    model_name=model_name,
                    promoted_only=True,
                )
                if row is not None:
                    items[model_name] = repo_model_runs.jsonable_row(row)
        if not items:
            raise HTTPException(status_code=404, detail="keine promoted expected-bps Modelle")
        return {"status": "ok", "models": items}

    @r.get("/learning/models/expected-bps/runs")
    def list_expected_bps_runs(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        items: dict[str, list[dict[str, Any]]] = {}
        with db_connect(settings.database_url) as conn:
            for model_name in BPS_REGRESSION_MODEL_NAMES:
                rows = repo_model_runs.list_model_runs(
                    conn,
                    model_name=model_name,
                    limit=limit,
                )
                items[model_name] = [repo_model_runs.jsonable_row(row) for row in rows]
        return {"status": "ok", "models": items}

    @r.post("/learning/models/expected-bps/train-now")
    def train_expected_bps(symbol: str | None = None, promote: bool = True) -> dict[str, Any]:
        try:
            with db_connect(settings.database_url) as conn:
                with conn.transaction():
                    report = train_expected_bps_models(
                        conn,
                        settings,
                        symbol=symbol,
                        promote=promote,
                    )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "report": report}

    @r.get("/learning/models/regime-classifier/latest")
    def latest_regime_classifier() -> dict[str, Any]:
        with db_connect(settings.database_url) as conn:
            row = repo_model_runs.get_latest_model_run(
                conn,
                model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
                promoted_only=True,
            )
        if row is None:
            raise HTTPException(status_code=404, detail="kein promoted market_regime_classifier")
        return {"status": "ok", "model": repo_model_runs.jsonable_row(row)}

    @r.get("/learning/models/regime-classifier/runs")
    def list_regime_classifier_runs(limit: int = 20) -> dict[str, Any]:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="limit 1..100")
        with db_connect(settings.database_url) as conn:
            rows = repo_model_runs.list_model_runs(
                conn,
                model_name=MARKET_REGIME_CLASSIFIER_MODEL_NAME,
                limit=limit,
            )
        return {
            "status": "ok",
            "count": len(rows),
            "items": [repo_model_runs.jsonable_row(row) for row in rows],
        }

    @r.get("/learning/training/specialists-readiness")
    def specialists_readiness(symbol: str | None = None) -> dict[str, Any]:
        """Read-only: Marktfamilien-Zaehlungen, Degrade-Hinweise — keine Modell-/Policy-Aenderung."""
        with db_connect(settings.database_url) as conn:
            report = audit_specialist_training_readiness(conn, settings, symbol=symbol)
        return {"status": "ok", "report": report}

    @r.post("/learning/models/regime-classifier/train-now")
    def train_regime_classifier(symbol: str | None = None, promote: bool = True) -> dict[str, Any]:
        try:
            with db_connect(settings.database_url) as conn:
                with conn.transaction():
                    report = train_market_regime_classifier(
                        conn,
                        settings,
                        symbol=symbol,
                        promote=promote,
                    )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "report": report}

    return r
