from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parents[4]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    sp = root / "shared" / "python" / "src"
    if sp.is_dir() and str(sp) not in sys.path:
        sys.path.insert(0, str(sp))


def main() -> None:
    import uvicorn

    _ensure_paths()
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    from audit_ledger.config import AuditLedgerSettings

    s = AuditLedgerSettings()
    uvicorn.run(
        "audit_ledger.app:build_app",
        factory=True,
        host=os.environ.get("AUDIT_LEDGER_BIND_HOST", "0.0.0.0"),
        port=int(os.environ.get("AUDIT_LEDGER_PORT", "8098")),
        log_level=os.environ.get("UVICORN_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
