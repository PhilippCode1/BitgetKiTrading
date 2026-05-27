"""Tenant-Trace-Anreicherung beim Live-Broker-Forward."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GW_SRC = REPO_ROOT / "services" / "api-gateway" / "src"
for candidate in (REPO_ROOT, GW_SRC):
    s = str(candidate)
    if s not in sys.path:
        sys.path.insert(0, s)

from api_gateway.live_broker_forward import (
    effective_tenant_for_live_broker_forward,
    merge_tenant_into_live_broker_body,
)


def test_merge_tenant_adds_trace_when_missing() -> None:
    out = merge_tenant_into_live_broker_body(
        {"reason": "test"},
        tenant_id="t-abc",
    )
    assert out["trace"]["tenant_id"] == "t-abc"
    assert out["reason"] == "test"


def test_merge_tenant_does_not_override_existing_trace() -> None:
    out = merge_tenant_into_live_broker_body(
        {"trace": {"tenant_id": "t-existing", "foo": "bar"}},
        tenant_id="t-new",
    )
    assert out["trace"]["tenant_id"] == "t-existing"


def test_merge_tenant_noop_without_tenant() -> None:
    body = {"trace": {"foo": "bar"}}
    assert merge_tenant_into_live_broker_body(body, tenant_id=None) is body


def test_effective_tenant_falls_back_to_commercial_default() -> None:
    class _Settings:
        commercial_default_tenant_id = "tenant-default"
        production = False

    assert (
        effective_tenant_for_live_broker_forward(_Settings(), None)
        == "tenant-default"
    )
    assert (
        effective_tenant_for_live_broker_forward(_Settings(), "jwt-tenant")
        == "jwt-tenant"
    )


def test_effective_tenant_no_fallback_in_vault_production(monkeypatch) -> None:
    class _Settings:
        commercial_default_tenant_id = "tenant-default"
        production = True

    monkeypatch.setenv("TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT", "true")
    assert effective_tenant_for_live_broker_forward(_Settings(), None) is None
    assert (
        effective_tenant_for_live_broker_forward(_Settings(), "jwt-tenant")
        == "jwt-tenant"
    )
