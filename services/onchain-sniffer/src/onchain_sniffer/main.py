from __future__ import annotations

import logging
import os

import uvicorn

from onchain_sniffer.app import build_app
from onchain_sniffer.config import OnchainSnifferSettings


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    s = OnchainSnifferSettings()
    uvicorn.run(
        build_app(),
        host=s.bind_host,
        port=s.bind_port,
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
