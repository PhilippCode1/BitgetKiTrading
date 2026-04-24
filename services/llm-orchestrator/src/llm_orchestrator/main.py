from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _ensure_shared_py_path() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    if sp.is_dir():
        s = str(sp)
        if s not in sys.path:
            sys.path.insert(0, s)


_ensure_shared_py_path()

logger = logging.getLogger("llm_orchestrator")


def main() -> None:
    import uvicorn

    try:
        from llm_orchestrator.config import LLMOrchestratorSettings
        from llm_orchestrator.quality_feedback_trace import log_quality_trace_startup

        log_quality_trace_startup(logger, LLMOrchestratorSettings())
    except Exception as exc:  # noqa: BLE001
        d1 = os.getenv("DATABASE_URL") or ""
        d2 = os.getenv("DATABASE_URL_DOCKER") or ""
        dsn = (d1 or d2).strip()
        env_en = (os.getenv("LLM_AI_EVAL_LOG_ENABLED", "true") or "").lower()
        on = env_en in ("1", "true", "yes", "on")
        if dsn and on:
            logger.info(
                "quality feedback trace: vermutlich aktiv (DATABASE_URL); %s",
                f"Einstellungen: {exc!r}",
            )
        else:
            logger.info("quality feedback trace: aus (kein DATABASE_URL / Feature aus)")

    logger.info("starting llm-orchestrator")
    uvicorn.run(
        "llm_orchestrator.app:app",
        host="0.0.0.0",
        port=int(os.getenv("LLM_ORCH_PORT", "8070")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
