from __future__ import annotations

import pytest

from shared_py.bitget.exchange_readiness import (
    assess_external_key_evidence,
    assess_permissions,
    assert_readonly_request,
    classify_http_status,
    path_uses_legacy_v1,
    readiness_verdict,
    server_time_skew_blockers,
)


def test_withdrawal_permission_fails() -> None:
    assessment = assess_permissions({"withdraw": True, "trade": True})
    assert assessment.status == "blocker"
    assert "withdrawal_permission_present" in assessment.blockers
    assert readiness_verdict(assessment.blockers, assessment.warnings) == "FAIL"


def test_external_key_evidence_blocks_withdrawal_permission() -> None:
    assessment = assess_external_key_evidence(
        {
            "schema_version": "bitget-exchange-readiness-v1",
            "environment": "production",
            "account_mode": "live_candidate",
            "read_permission": True,
            "trade_permission": True,
            "withdrawal_permission": True,
            "ip_allowlist_enabled": True,
            "account_protection_enabled": True,
            "api_version": "v2",
            "instrument_scope": "USDT-FUTURES",
            "reviewed_by": "external-security-review",
            "reviewed_at": "2026-04-26T00:00:00Z",
            "evidence_reference": "external-ticket-123",
            "owner_signoff": True,
        }
    )
    assert assessment.status == "FAIL"
    assert "withdrawal_permission_not_false" in assessment.blockers


def test_external_key_evidence_requires_owner_signoff_warning() -> None:
    assessment = assess_external_key_evidence(
        {
            "schema_version": "bitget-exchange-readiness-v1",
            "environment": "production",
            "account_mode": "live_candidate",
            "read_permission": True,
            "trade_permission": True,
            "withdrawal_permission": False,
            "ip_allowlist_enabled": True,
            "account_protection_enabled": True,
            "api_version": "v2",
            "instrument_scope": "USDT-FUTURES",
            "reviewed_by": "external-security-review",
            "reviewed_at": "2026-04-26T00:00:00Z",
            "evidence_reference": "external-ticket-123",
            "owner_signoff": False,
        }
    )
    assert assessment.status == "PASS_WITH_WARNINGS"
    assert assessment.blockers == []
    assert "owner_signoff_missing_external_required" in assessment.warnings


def test_unclear_permission_blocks_live_with_warning() -> None:
    assessment = assess_permissions(None)
    assert assessment.status == "warning"
    assert "permission_evidence_missing_live_write_blocked" in assessment.warnings


def test_server_time_skew_fails() -> None:
    blockers = server_time_skew_blockers(10_000, max_skew_ms=5_000)
    assert blockers == ["server_time_skew_exceeds_budget:10000ms>5000ms"]


def test_private_auth_fail_classified() -> None:
    assert classify_http_status(401) == "auth"
    assert classify_http_status(403) == "permission"


def test_rate_limit_classified() -> None:
    assert classify_http_status(429) == "rate_limit"


def test_v1_api_hint_is_risk() -> None:
    assert path_uses_legacy_v1("/api/v1/mix/order/placeOrder")
    assert not path_uses_legacy_v1("/api/v2/public/time")


def test_readonly_mode_cannot_send_order() -> None:
    with pytest.raises(ValueError):
        assert_readonly_request("POST", "/api/v2/mix/order/place-order")
    with pytest.raises(ValueError):
        assert_readonly_request("GET", "/api/v2/mix/order/cancel-order")
