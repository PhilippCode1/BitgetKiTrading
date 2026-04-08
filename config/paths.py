"""
Monorepo-Pfade fuer ENV-Dateien (keine zirkulaeren Imports zu bootstrap/settings).

resolve_standard_env_files() wird von BaseServiceSettings bei jeder Settings-Instanz
aufgerufen (DotEnvSettingsSource), nicht als festes Tuple beim ersten Import dieses
Moduls. So gelten COMPOSE_ENV_FILE / CONFIG_ENV_FILE zur Prozess-Startzeit zuverlaessig.
In Compose setzt docker-compose ``CONFIG_ENV_FILE`` aus derselben Quelle wie der Host.
"""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_DIR = Path(__file__).resolve().parent
REPO_ROOT = _CONFIG_DIR.parent

_PROFILE_TO_ENV_FILE = {
    "local": ".env.local",
    "development": ".env.local",
    "shadow": ".env.shadow",
    "staging": ".env.shadow",
    "production": ".env.production",
    "prod": ".env.production",
    "test": ".env.test",
}


def _append_candidate(out: list[str], raw: str) -> None:
    normalized = str(raw).strip()
    if not normalized:
        return
    if Path(normalized).is_absolute():
        value = str(Path(normalized))
        if value not in out:
            out.append(value)
        return
    repo_value = str(REPO_ROOT / normalized)
    if repo_value not in out:
        out.append(repo_value)
    if normalized not in out:
        out.append(normalized)


def resolve_standard_env_files() -> tuple[str, ...]:
    candidates: list[str] = []

    for env_name in ("CONFIG_ENV_FILE", "COMPOSE_ENV_FILE", "ENV_PROFILE_FILE"):
        raw = os.environ.get(env_name, "")
        if raw:
            _append_candidate(candidates, raw)

    profile_name = ""
    for env_name in ("STACK_PROFILE", "APP_ENV"):
        raw = os.environ.get(env_name, "").strip().lower()
        if raw:
            profile_name = raw
            break
    if profile_name:
        env_file = _PROFILE_TO_ENV_FILE.get(profile_name)
        if env_file:
            _append_candidate(candidates, env_file)

    production_like = (
        profile_name in ("production", "prod")
        or (os.environ.get("PRODUCTION") or "").strip().lower() in ("true", "1", "yes")
    )
    env_files_target_prod = False
    for env_name in ("CONFIG_ENV_FILE", "COMPOSE_ENV_FILE", "ENV_PROFILE_FILE"):
        raw = (os.environ.get(env_name) or "").strip().lower()
        if raw.endswith(".env.production") or ".env.production" in raw:
            env_files_target_prod = True
            break

    # Fallback `.env.local` nur fuer lokale/Dev-Workflows — nie nach Production-Profil mischen
    # (sonst ueberschreibt lokale Keys z. B. Secrets/URLs aus `.env.production`).
    if not production_like and not env_files_target_prod:
        _append_candidate(candidates, ".env.local")
    return tuple(candidates)
