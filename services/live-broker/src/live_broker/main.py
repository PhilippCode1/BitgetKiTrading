from __future__ import annotations

import uvicorn

from live_broker.config import LiveBrokerSettings


def main() -> None:
    settings = LiveBrokerSettings()
    uvicorn.run(
        "live_broker.app:app",
        host="0.0.0.0",
        port=settings.live_broker_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
