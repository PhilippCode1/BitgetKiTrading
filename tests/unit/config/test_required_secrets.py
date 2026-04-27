from __future__ import annotations

from types import SimpleNamespace

import pytest

from config.required_secrets import (
    RequiredSecretsError,
    required_env_names_for_env_file_profile,
    validate_required_secrets,
)


def test_union_local_includes_gateway_secret_once() -> None:
    keys = required_env_names_for_env_file_profile(profile="local")
    assert "GATEWAY_JWT_SECRET" in keys
    assert keys.count("DATABASE_URL") == 1


def test_staging_and_shadow_profiles_same_union() -> None:
    assert required_env_names_for_env_file_profile(profile="staging") == required_env_names_for_env_file_profile(
        profile="shadow",
    )


def test_shadow_boot_uses_staging_matrix_column() -> None:
    env = {k: "z" * 32 for k in required_env_names_for_env_file_profile(profile="staging")}
    settings = SimpleNamespace(production=True, app_env="shadow")
    validate_required_secrets("api-gateway", settings, environ=env)


def test_market_stream_not_required_gateway_jwt() -> None:
    env = {
        k: "x" * 32
        for k in required_env_names_for_env_file_profile(profile="local")
        if k != "GATEWAY_JWT_SECRET"
    }
    settings = SimpleNamespace(production=False)
    validate_required_secrets("market-stream", settings, environ=env)


def test_api_gateway_requires_gateway_jwt() -> None:
    env = {
        k: "x" * 32
        for k in required_env_names_for_env_file_profile(profile="local")
        if k != "GATEWAY_JWT_SECRET"
    }
    settings = SimpleNamespace(production=False)
    with pytest.raises(RequiredSecretsError) as ei:
        validate_required_secrets("api-gateway", settings, environ=env)
    assert "GATEWAY_JWT_SECRET" in str(ei.value)


def test_missing_internal_key_raises() -> None:
    env = {
        k: "y" * 32
        for k in required_env_names_for_env_file_profile(profile="local")
        if k != "INTERNAL_API_KEY"
    }
    settings = SimpleNamespace(production=False)
    with pytest.raises(RequiredSecretsError) as ei:
        validate_required_secrets("signal-engine", settings, environ=env)
    assert "INTERNAL_API_KEY" in str(ei.value)
