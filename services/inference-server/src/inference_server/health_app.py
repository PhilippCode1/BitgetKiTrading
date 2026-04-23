from __future__ import annotations

from typing import Any

from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="inference-server", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "inference-server"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        return {"ready": True, "service": "inference-server"}

    return app
