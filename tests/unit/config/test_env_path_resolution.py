from __future__ import annotations

import importlib


def test_resolve_standard_env_files_prefers_profile(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "shadow")
    from config import paths as paths_module

    importlib.reload(paths_module)
    resolved = paths_module.resolve_standard_env_files()
    assert any(item.endswith(".env.shadow") for item in resolved)
    assert any(item.endswith(".env.local") for item in resolved)


def test_resolve_standard_env_files_prefers_explicit_env_file(monkeypatch) -> None:
    for key in ("APP_ENV", "STACK_PROFILE", "COMPOSE_ENV_FILE", "ENV_PROFILE_FILE", "PRODUCTION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CONFIG_ENV_FILE", ".env.production")
    from config import paths as paths_module

    importlib.reload(paths_module)
    resolved = paths_module.resolve_standard_env_files()
    assert resolved[0].endswith(".env.production")
    assert not any(item.endswith(".env.local") for item in resolved)


def test_resolve_standard_env_files_skips_local_for_production_profile(monkeypatch) -> None:
    monkeypatch.delenv("COMPOSE_ENV_FILE", raising=False)
    monkeypatch.delenv("CONFIG_ENV_FILE", raising=False)
    monkeypatch.delenv("ENV_PROFILE_FILE", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("PRODUCTION", raising=False)
    from config import paths as paths_module

    importlib.reload(paths_module)
    resolved = paths_module.resolve_standard_env_files()
    assert any(item.endswith(".env.production") for item in resolved)
    assert not any(item.endswith(".env.local") for item in resolved)


def test_resolve_standard_env_files_skips_local_when_compose_targets_production(monkeypatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.setenv("COMPOSE_ENV_FILE", ".env.production")
    from config import paths as paths_module

    importlib.reload(paths_module)
    resolved = paths_module.resolve_standard_env_files()
    assert not any(item.endswith(".env.local") for item in resolved)


def test_resolve_standard_env_files_config_env_file_matches_compose(monkeypatch) -> None:
    """CONFIG_ENV_FILE (wie in Compose x-app-runtime-env) hat Vorrang vor APP_ENV-Mapping."""
    monkeypatch.delenv("COMPOSE_ENV_FILE", raising=False)
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("CONFIG_ENV_FILE", ".env.shadow")
    from config import paths as paths_module

    importlib.reload(paths_module)
    resolved = paths_module.resolve_standard_env_files()
    assert resolved[0].endswith(".env.shadow")
