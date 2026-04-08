from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import uvicorn


def _ensure_monorepo_root() -> None:
    root = Path(__file__).resolve().parents[4]
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)


_ensure_monorepo_root()

logger = logging.getLogger("alert_engine")


def main() -> None:
    port = int(os.getenv("ALERT_ENGINE_PORT", "8100"))
    uvicorn.run(
        "alert_engine.app:app",
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
