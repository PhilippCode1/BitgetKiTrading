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

logger = logging.getLogger("news_engine")


def main() -> None:
    import uvicorn

    logger.info("starting news-engine")
    uvicorn.run(
        "news_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("NEWS_ENGINE_PORT", "8060")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
