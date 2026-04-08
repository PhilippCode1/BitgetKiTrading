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

logger = logging.getLogger("paper_broker")


def main() -> None:
    import uvicorn

    logger.info("starting paper-broker")
    uvicorn.run(
        "paper_broker.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PAPER_BROKER_PORT", "8085")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
