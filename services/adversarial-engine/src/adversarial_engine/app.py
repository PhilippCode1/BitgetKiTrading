from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

from adversarial_engine.api.routes import build_health_router, build_router
from adversarial_engine.config import AdversarialEngineSettings


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


_ensure_paths()


def create_app() -> FastAPI:
    from config.bootstrap import bootstrap_from_settings
    from shared_py.observability import instrument_fastapi

    settings = AdversarialEngineSettings()
    bootstrap_from_settings("adversarial-engine", settings)
    app = FastAPI(
        title="adversarial-engine",
        version="0.1.0",
        description="Adversarial Market Simulator (WGAN-GP) — toxische Stress-Batches als Arrow IPC.",
    )
    app.include_router(build_health_router(settings))
    app.include_router(build_router(settings))
    instrument_fastapi(app, "adversarial-engine")
    return app


app = create_app()
