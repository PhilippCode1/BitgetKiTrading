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


def main() -> None:
    import uvicorn

    _ensure_paths()
    from adversarial_engine.config import AdversarialEngineSettings

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = AdversarialEngineSettings()
    uvicorn.run(
        "adversarial_engine.app:app",
        host="0.0.0.0",
        port=int(settings.adversarial_engine_port),
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
