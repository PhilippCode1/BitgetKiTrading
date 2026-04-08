from __future__ import annotations

import logging
import os

logger = logging.getLogger("drawing_engine")


def main() -> None:
    import uvicorn

    logger.info("starting drawing-engine")
    uvicorn.run(
        "drawing_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("DRAWING_ENGINE_PORT", "8040")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
