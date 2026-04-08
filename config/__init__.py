"""
Zentrale Laufzeit-Konfiguration und Logging-Setup (Prompt 30).

Das Paket liegt unter dem Repo-Root; ``PYTHONPATH`` muss den Repo-Root enthalten
(z. B. ``PYTHONPATH=/app:/app/shared/python/src`` in Docker).
"""

from __future__ import annotations

from config.bootstrap import bootstrap_from_settings, bootstrap_service
from config.logging_config import setup_logging
from config.paths import REPO_ROOT, resolve_standard_env_files
from config.settings import (
    MIN_PRODUCTION_SECRET_LEN,
    ApiAuthMode,
    BaseServiceSettings,
    ContractConfigMode,
    ExecutionMode,
    StrategyExecutionMode,
    StrategyRegistryStatus,
    TelegramMode,
    TradingRuntimeMode,
    TriggerType,
    emit_secret_management_warning,
)

__all__ = [
    "ApiAuthMode",
    "BaseServiceSettings",
    "bootstrap_from_settings",
    "bootstrap_service",
    "ContractConfigMode",
    "emit_secret_management_warning",
    "ExecutionMode",
    "MIN_PRODUCTION_SECRET_LEN",
    "REPO_ROOT",
    "resolve_standard_env_files",
    "setup_logging",
    "StrategyExecutionMode",
    "StrategyRegistryStatus",
    "TelegramMode",
    "TradingRuntimeMode",
    "TriggerType",
]
