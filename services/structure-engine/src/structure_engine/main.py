from __future__ import annotations

import logging
import os

logger = logging.getLogger("structure_engine")


def main() -> None:
    import uvicorn

    logger.info("starting structure-engine")
    uvicorn.run(
        "structure_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("STRUCTURE_ENGINE_PORT", "8030")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
