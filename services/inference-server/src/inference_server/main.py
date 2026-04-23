from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import grpc
import uvicorn
from shared_py.rpc.apex_timesfm.v1 import timesfm_inference_pb2_grpc as pb2_grpc

from inference_server.config import InferenceServerSettings
from inference_server.grpc_servicer import TimesFmInferenceServicer
from inference_server.embed_routes import build_embedding_router
from inference_server.health_app import create_app
from inference_server.timesfm_model import TimesFmModelEngine

logger = logging.getLogger("inference_server.main")


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    if sp.is_dir():
        s = str(sp)
        if s not in sys.path:
            sys.path.insert(0, s)
    cfg = root / "config"
    if cfg.is_dir():
        s2 = str(root)
        if s2 not in sys.path:
            sys.path.insert(0, s2)


async def _serve() -> None:
    _ensure_paths()
    from config.bootstrap import bootstrap_from_settings

    settings = InferenceServerSettings()
    bootstrap_from_settings("inference-server", settings)
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine = TimesFmModelEngine(model_id=settings.timesfm_model_id)
    servicer = TimesFmInferenceServicer(settings, engine)
    server = grpc.aio.server(
        options=(
            ("grpc.max_send_message_length", 64 * 1024 * 1024),
            ("grpc.max_receive_message_length", 64 * 1024 * 1024),
        )
    )
    pb2_grpc.add_TimesFmInferenceServicer_to_server(servicer, server)
    grpc_addr = f"0.0.0.0:{settings.inference_grpc_port}"
    server.add_insecure_port(grpc_addr)
    await server.start()
    logger.info("gRPC TimesFmInference auf %s (Modell=%s)", grpc_addr, settings.timesfm_model_id)

    app = create_app()
    if settings.embedding_enabled:
        app.include_router(build_embedding_router(settings))
    uv_cfg = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=settings.inference_http_port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
    uv_server = uvicorn.Server(uv_cfg)
    http_task = asyncio.create_task(uv_server.serve(), name="inference-http")
    try:
        await server.wait_for_termination()
    finally:
        http_task.cancel()
        try:
            await http_task
        except asyncio.CancelledError:
            pass
        await server.stop(5.0)


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
