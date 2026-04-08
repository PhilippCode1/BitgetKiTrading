from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _ensure_monorepo_root() -> None:
    root = Path(__file__).resolve().parents[4]
    s = str(root)
    if s not in sys.path:
        sys.path.insert(0, s)


_ensure_monorepo_root()

logger = logging.getLogger("monitor_engine")


def main() -> None:
    import uvicorn

    port = int(os.getenv("MONITOR_ENGINE_PORT", "8110"))
    uvicorn.run(
        "monitor_engine.app:app",
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
