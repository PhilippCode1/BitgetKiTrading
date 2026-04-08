from __future__ import annotations

import logging

import uvicorn

from market_stream.app import MarketStreamSettings


def main() -> None:
    settings = MarketStreamSettings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("market_stream").info(
        "starting market-stream on port %s",
        settings.market_stream_port,
    )
    uvicorn.run(
        "market_stream.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.market_stream_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
