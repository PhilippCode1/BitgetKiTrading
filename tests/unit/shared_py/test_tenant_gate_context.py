"""Tests fuer shared_py.tenant_gate_context."""

from __future__ import annotations

from shared_py.tenant_gate_context import resolve_modul_mate_gate_tenant_id


def test_resolve_prefers_trace_tenant_over_config() -> None:
    tid = resolve_modul_mate_gate_tenant_id(
        config_tenant_id="default",
        trace={"tenant_id": "tenant_alpha"},
    )
    assert tid == "tenant_alpha"


def test_resolve_falls_back_to_config_when_trace_missing() -> None:
    tid = resolve_modul_mate_gate_tenant_id(
        config_tenant_id="tenant_config",
        trace={"correlation_id": "x"},
    )
    assert tid == "tenant_config"


def test_resolve_ignores_invalid_trace_tenant() -> None:
    tid = resolve_modul_mate_gate_tenant_id(
        config_tenant_id="tenant_config",
        trace={"tenant_id": "bad id with spaces"},
    )
    assert tid == "tenant_config"
