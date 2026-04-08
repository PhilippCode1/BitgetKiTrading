from __future__ import annotations

import logging
import os

logger = logging.getLogger("feature_engine")


def main() -> None:
    import uvicorn

    logger.info("starting feature-engine")
    uvicorn.run(
        "feature_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("FEATURE_ENGINE_PORT", "8020")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
