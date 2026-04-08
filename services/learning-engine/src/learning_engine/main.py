from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    sp = root / "shared" / "python" / "src"
    for p in (root, sp):
        if p.is_dir():
            s = str(p)
            if s not in sys.path:
                sys.path.insert(0, s)


_ensure_paths()

logger = logging.getLogger("learning_engine")


def main() -> None:
    import uvicorn

    logger.info("starting learning-engine")
    uvicorn.run(
        "learning_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("LEARNING_ENGINE_PORT", "8090")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
