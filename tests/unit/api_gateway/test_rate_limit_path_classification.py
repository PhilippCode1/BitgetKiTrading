"""Rate-Limit-Pfadklassifikation ohne Redis (Security-/Policy-Evidenz)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import api_gateway.rate_limit as rl


@pytest.mark.security
def test_classify_commerce_and_events_sensitive() -> None:
    assert rl._classify_path("/v1/llm/operator/explain") == "sensitive"
    assert rl._classify_path("/v1/commerce/plans") == "sensitive"
    assert rl._classify_path("/events/tail") == "sensitive"
    assert rl._classify_path("/events/dlq/foo") == "sensitive"
    assert rl._classify_path("/db/schema") == "sensitive"


@pytest.mark.security
def test_classify_public_health_routes_not_used_by_middleware_but_paths() -> None:
    assert rl._classify_path("/v1/public/ping") == "public"


@pytest.mark.security
def test_safety_mutation_paths() -> None:
    assert rl._is_safety_mutation("/v1/live-broker/safety/orders/cancel-all", "POST")
    assert not rl._is_safety_mutation("/v1/live-broker/safety/orders/cancel-all", "GET")
    assert rl._is_safety_mutation(
        "/v1/foo/executions/x/operator-release", "POST"
    )
    assert not rl._is_safety_mutation("/v1/admin/foo", "POST")


@pytest.mark.security
def test_client_bucket_key_prefers_authorization_hash() -> None:
    req = Mock()
    req.headers = {"authorization": "Bearer secret-token"}
    req.client = None
    k = rl._client_bucket_key(req)
    assert k.startswith("a:")


@pytest.mark.security
def test_limit_for_class_respects_settings_fields() -> None:
    settings = SimpleNamespace(
        gateway_rl_admin_mutate_per_minute=7,
        gateway_rl_sensitive_per_minute=120,
        gateway_rl_public_per_minute=600,
    )
    assert rl._limit_for_class(settings, "admin", is_admin_mutate=True) == 7
    assert rl._limit_for_class(settings, "sensitive", is_admin_mutate=False) == 120
    assert rl._limit_for_class(settings, "public", is_admin_mutate=False) == 600
