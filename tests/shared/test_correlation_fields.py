"""Korrelationsfelder fuer strukturierte Logs."""

from __future__ import annotations

from shared_py.observability.correlation import log_correlation_fields


def test_log_correlation_includes_gateway_audit_and_tenant() -> None:
    extra = log_correlation_fields(
        gateway_audit_id="550e8400-e29b-41d4-a716-446655440000",
        tenant_id="acme",
        signal_id="sig-1",
        execution_id="exec-1",
    )
    assert extra["corr_gateway_audit_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert extra["corr_tenant_id"] == "acme"
    assert extra["corr_signal_id"] == "sig-1"
    assert extra["corr_execution_id"] == "exec-1"
