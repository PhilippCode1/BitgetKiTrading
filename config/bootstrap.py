"""
Service-Bootstrap: Logging, Secret-Hinweis, Settings-Snapshots ohne Secrets.

bootstrap_service() ist deprecated — bootstrap_from_settings() nach Settings().
"""

from __future__ import annotations

import json
import logging
import warnings
from pathlib import Path
from typing import Any, TypeVar

from config.datastore_dsn import log_effective_datastores
from config.logging_config import log_startup_line, setup_logging
from config.required_secrets import validate_required_secrets
from config.settings import BaseServiceSettings, emit_secret_management_warning

TSettings = TypeVar("TSettings", bound=BaseServiceSettings)


def _hydrate_os_environ_from_dotenv_files() -> None:
    """
    Pydantic laedt Dotenv in Settings, setzt aber nicht automatisch os.environ.
    validate_required_secrets prueft die Matrix gegen os.environ — daher fehlende
    Keys bei CLI/Tools (z. B. verify_bitget_rest) ohne diese Hydration.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    from config.paths import resolve_standard_env_files

    for raw in resolve_standard_env_files():
        path = Path(raw)
        if path.is_file():
            load_dotenv(path, override=False)


_SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "password",
    "token",
    "passphrase",
    "api_key",
    "apikey",
    "credential",
    "authorization",
    "private_key",
    "webhook",
    "bot_token",
)


def _is_sensitive_field_name(name: str) -> bool:
    n = name.lower()
    return any(f in n for f in _SENSITIVE_KEY_FRAGMENTS) or n.endswith("_key")


def _redact_dsn_url(value: str) -> str:
    """Entfernt User/Pass aus typischen SQL/Redis-URLs fuer Logs."""
    s = value.strip()
    if not s or "@" not in s or "://" not in s:
        return "***" if s else ""
    scheme, rest = s.split("://", 1)
    if "@" in rest:
        hostpart = rest.split("@", 1)[1]
        return f"{scheme}://***@{hostpart}"
    return "***"


def redact_settings_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Flaches dict fuer Logs — keine Secrets, keine vollen DSNs."""
    out: dict[str, Any] = {}
    for k, v in data.items():
        if _is_sensitive_field_name(k):
            out[k] = "***"
        elif isinstance(v, str) and k in (
            "database_url",
            "redis_url",
            "database_url_docker",
            "redis_url_docker",
        ):
            out[k] = _redact_dsn_url(v)
        elif isinstance(v, dict):
            out[k] = redact_settings_dict(v)
        else:
            out[k] = v
    return out


def settings_public_snapshot(settings: BaseServiceSettings) -> dict[str, Any]:
    """Nur typische Betriebsparameter (kein vollstaendiger Dump)."""
    names = (
        "production",
        "app_env",
        "debug",
        "execution_mode",
        "strategy_execution_mode",
        "shadow_trade_enable",
        "live_trade_enable",
        "live_broker_enabled",
        "bitget_demo_enabled",
        "news_fixture_mode",
        "llm_use_fake_provider",
        "paper_sim_mode",
        "paper_contract_config_mode",
        "telegram_dry_run",
        "log_level",
        "log_format",
        "vault_mode",
        "api_auth_mode",
        "risk_allowed_leverage_min",
        "risk_allowed_leverage_max",
        "risk_elevated_leverage_live_ack",
    )
    snap: dict[str, Any] = {}
    for name in names:
        if hasattr(settings, name):
            snap[name] = getattr(settings, name)
    # Gateway-spezifisch (optional)
    for name in (
        "gateway_enforce_sensitive_auth",
        "gateway_allow_legacy_admin_token",
        "app_port",
        "signal_engine_port",
        "feature_engine_port",
        "structure_engine_port",
        "drawing_engine_port",
        "news_engine_port",
        "llm_orch_port",
        "paper_broker_port",
        "learning_engine_port",
        "alert_engine_port",
        "monitor_engine_port",
        "market_stream_port",
        "live_broker_port",
    ):
        if hasattr(settings, name):
            snap[name] = getattr(settings, name)
    return snap


def log_bootstrap_settings(
    logger: logging.Logger,
    settings: BaseServiceSettings,
) -> None:
    """INFO: kompakte Betriebsparameter; DEBUG: redacted JSON-Subset."""
    snap = settings_public_snapshot(settings)
    logger.info("bootstrap_settings %s", json.dumps(snap, default=str, sort_keys=True))
    try:
        full = settings.model_dump(mode="json")
    except Exception:  # pragma: no cover
        logger.debug("bootstrap_settings_full_dump_skipped")
        return
    red = redact_settings_dict(full)
    logger.debug(
        "bootstrap_settings_redacted %s",
        json.dumps(red, default=str, sort_keys=True),
    )


def bootstrap_from_settings(service_name: str, settings: TSettings) -> TSettings:
    """
    Root-Logging aus den **tatsaechlich** geladenen Settings; Secret-Hinweis + Snapshot.
    Fail-fast: pydantic Settings() plus validate_required_secrets (Matrix).
    """
    _hydrate_os_environ_from_dotenv_files()
    setup_logging(service_name, settings.log_level, settings.log_format)
    logger = logging.getLogger(service_name.replace("-", "_"))
    validate_required_secrets(service_name, settings)
    emit_secret_management_warning(logger, settings)
    log_startup_line(logger, service_name, settings)
    log_effective_datastores(logger, settings)
    log_bootstrap_settings(logger, settings)
    return settings


def bootstrap_service(service_name: str) -> BaseServiceSettings:
    """
    .. deprecated::
        Laedt nur `BaseServiceSettings()` — kann von service-spezifischen ENV abweichen.
        Verwende `bootstrap_from_settings(service_name, MyServiceSettings())`.
    """
    warnings.warn(
        "bootstrap_service() ist deprecated — nutze bootstrap_from_settings() "
        "mit der konkreten Settings-Klasse.",
        DeprecationWarning,
        stacklevel=2,
    )
    settings = BaseServiceSettings()
    return bootstrap_from_settings(service_name, settings)
