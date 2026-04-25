from __future__ import annotations

import pytest

from shared_py.bitget.exchange_readiness import (
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
