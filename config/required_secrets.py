"""
Pflicht-ENV je Service und Profil — Daten aus required_secrets_matrix.json.

Wird beim Service-Boot aufgerufen (bootstrap_from_settings), zusaetzlich zu pydantic.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from config.settings import BaseServiceSettings

_MATRIX_PATH = Path(__file__).resolve().parent / "required_secrets_matrix.json"


class RequiredSecretsError(RuntimeError):
    """Fehlende oder ungueltige Pflicht-Variablen laut Matrix."""


def _load_matrix() -> dict[str, Any]:
    raw = _MATRIX_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


def _bad_value(val: str | None) -> bool:
    if val is None:
        return True
    t = val.strip()
    if not t:
        return True
    u = t.upper()
    if "<SET_ME>" in u or u == "SET_ME" or u == "CHANGE_ME":
        return True
    return False


def _service_matches(services: str | list[str], service_name: str) -> bool:
    if services == "*" or services == ["*"]:
        return True
    if isinstance(services, list):
        return service_name in services
    raise ValueError(f"invalid services spec: {services!r}")


def _matrix_phase_for_boot(settings: BaseServiceSettings) -> str:
    """
    Matrix-Spalte fuer Service-Boot: local vs. staging (Pre-Prod / APP_ENV=shadow) vs. production.
    """
    production = bool(getattr(settings, "production", False))
    app_env = str(getattr(settings, "app_env", "") or "").lower()
    if not production and app_env in ("local", "development", "test"):
        return "local"
    if app_env == "production":
        return "production"
    if app_env == "shadow":
        return "staging"
    if production:
        return "production"
    return "local"


def validate_required_secrets(
    service_name: str,
    settings: BaseServiceSettings,
    *,
    environ: Mapping[str, str] | None = None,
) -> None:
    """
    Fail-fast nach Matrix: nur Eintraege, die fuer diesen Service und das Profil gelten.

    Liest Werte aus os.environ oder aus dem Argument ``environ``.
    """
    envmap = environ if environ is not None else os.environ
    data = _load_matrix()
    entries: list[dict[str, Any]] = list(data.get("entries") or [])
    phase_key = _matrix_phase_for_boot(settings)

    missing: list[str] = []
    for entry in entries:
        if entry.get(phase_key) != "required":
            continue
        svc = entry.get("services")
        if not _service_matches(svc, service_name):
            continue
        name = str(entry.get("env") or "").strip()
        if not name:
            continue
        if _bad_value(envmap.get(name)):
            missing.append(name)

    if missing:
        detail = "\n  ".join(sorted(set(missing)))
        msg = (
            f"validate_required_secrets({service_name!r}, {phase_key}): "
            "fehlende oder ungueltige Pflicht-ENV (Platzhalter/leer). "
            "Siehe config/required_secrets_matrix.json und docs/SECRETS_MATRIX.md:\n  "
        )
        raise RequiredSecretsError(msg + detail)


def required_env_names_for_env_file_profile(
    *,
    profile: str,
    with_dashboard_operator: bool = False,
) -> list[str]:
    """
    Wie validate_env_profile: Union aller Keys fuer das Profil.

    local → Spalte ``local``; shadow/staging → ``staging``; production → ``production``.

    ``with_dashboard_operator``: erzwingt zusaetzlich ``DASHBOARD_GATEWAY_AUTHORIZATION``
    fuer **local** (nach JWT-Mint), da die Matrix-Spalte ``local`` dafuer ``optional`` ist.
    """
    data = _load_matrix()
    entries: list[dict[str, Any]] = list(data.get("entries") or [])
    if profile == "local":
        phase_key = "local"
    elif profile in ("shadow", "staging"):
        phase_key = "staging"
    else:
        phase_key = "production"
    names: list[str] = []
    for entry in entries:
        if entry.get(phase_key) != "required":
            continue
        name = str(entry.get("env") or "").strip()
        if name:
            names.append(name)
    if with_dashboard_operator and profile == "local":
        names.append("DASHBOARD_GATEWAY_AUTHORIZATION")
    return list(dict.fromkeys(names))
