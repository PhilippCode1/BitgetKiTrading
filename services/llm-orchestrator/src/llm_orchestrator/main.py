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

    logger.info("starting llm-orchestrator")
    uvicorn.run(
        "llm_orchestrator.app:app",
        host="0.0.0.0",
        port=int(os.getenv("LLM_ORCH_PORT", "8070")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
