"""
Strukturiertes Logging: plain oder JSON (Felder inkl. service, level, timestamp).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

try:
    from pythonjsonlogger import jsonlogger
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal CI bootstrap envs
    jsonlogger = None  # type: ignore[assignment]

try:
    from shared_py.observability.request_context import RequestContextLoggingFilter
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal CI bootstrap envs
    class RequestContextLoggingFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
            return True


class _ServiceNameFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service  # type: ignore[attr-defined]
        return True


def setup_logging(service_name: str, level: str, log_format: str = "plain") -> None:
    """
    Root-Logger konfigurieren (idempotent genug fuer wiederholte Aufrufe in Tests).
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    lvl = getattr(logging, str(level).upper(), logging.INFO)
    root.setLevel(lvl)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_ServiceNameFilter(service_name))
    handler.addFilter(RequestContextLoggingFilter())

    fmt = str(log_format).strip().lower()
    if fmt == "json" and jsonlogger is not None:
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            "%(timestamp)s %(level)s %(service)s %(name)s %(message)s",
            rename_fields={
                "levelname": "level",
                "asctime": "timestamp",
            },
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(service)s | %(name)s | %(message)s"
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)


def log_startup_line(logger: logging.Logger, service: str, settings: Any) -> None:
    """Einheitliche Startzeile (ohne Secrets)."""
    prod = getattr(settings, "production", False)
    env = getattr(settings, "app_env", "")
    exec_mode = getattr(settings, "execution_mode", "")
    mode = "production" if prod else "non-production"
    logger.info(
        "starting %s in %s mode APP_ENV=%s EXECUTION_MODE=%s",
        service,
        mode,
        env,
        exec_mode,
    )
