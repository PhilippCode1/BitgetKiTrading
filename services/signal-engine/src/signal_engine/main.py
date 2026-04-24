from __future__ import annotations

"""
Entry-Point: HTTP-Server. Multi-Asset-Risk (Spot/Margin/Futures) wird in
`hybrid_decision` / `risk_governor` / `specialists` umgesetzt, nicht hier.
"""

import logging
import os

logger = logging.getLogger("signal_engine")


def main() -> None:
    import uvicorn

    logger.info("starting signal-engine")
    uvicorn.run(
        "signal_engine.app:app",
        host="0.0.0.0",
        port=int(os.getenv("SIGNAL_ENGINE_PORT", "8050")),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
