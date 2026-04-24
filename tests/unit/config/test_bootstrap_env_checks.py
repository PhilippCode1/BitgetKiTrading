from __future__ import annotations

from config.bootstrap_env_checks import bootstrap_env_consistency_issues


def test_api_gateway_url_must_not_use_docker_service_name_on_host() -> None:
    env = {
        "API_GATEWAY_URL": "http://api-gateway:8000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "INTERNAL_API_KEY": "x" * 32,
    }
    issues = bootstrap_env_consistency_issues(env, profile="local")
    assert any("API_GATEWAY_URL" in i and "api-gateway" in i for i in issues)


def test_health_url_loopback_rejected_in_shadow() -> None:
    env = {
        "API_GATEWAY_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "HEALTH_URL_MARKET_STREAM": "http://127.0.0.1:8010/ready",
        "INTERNAL_API_KEY": "x" * 32,
    }
    issues = bootstrap_env_consistency_issues(env, profile="shadow")
    assert any("HEALTH_URL_MARKET_STREAM" in i for i in issues)


def test_clean_local_like_env_has_no_consistency_issues() -> None:
    env = {
        "API_GATEWAY_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
        "INTERNAL_API_KEY": "x" * 32,
    }
    assert bootstrap_env_consistency_issues(env, profile="local") == []


def test_shadow_profile_rejects_loopback_for_public_url_keys() -> None:
    env = {
        "API_GATEWAY_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8000",
        "NEXT_PUBLIC_WS_BASE_URL": "ws://127.0.0.1:8000",
        "INTERNAL_API_KEY": "x" * 32,
    }
    issues = bootstrap_env_consistency_issues(env, profile="shadow")
    assert any("API_GATEWAY_URL" in i for i in issues)
    assert any("NEXT_PUBLIC_API_BASE_URL" in i for i in issues)
    assert any("NEXT_PUBLIC_WS_BASE_URL" in i for i in issues)
