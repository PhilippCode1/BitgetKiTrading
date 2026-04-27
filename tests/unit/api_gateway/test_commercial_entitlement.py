"""623 / Prompt 45: KI-Premium-Entitlement (DB-Logik gemockt, ohne Postgres)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from api_gateway.auth import GatewayAuthContext
from api_gateway.deps import (
    _evaluate_commercial_feature_access,
    commercial_feature_access_check_or_http,
)
from fastapi import HTTPException


def test_free_plan_denies_deep_analysis() -> None:
    conn = MagicMock()
    rows = [
        {
            "plan_entitlement_key": "ai_deep_analysis",
            "min_prepaid_balance_list_usd": Decimal("0"),
        },
        {
            "entitlements_json": {"llm": "none", "ai_deep_analysis": False},
            "plan_id": "free",
        },
    ]

    def _ex(q: str, p: object) -> MagicMock:
        m = MagicMock()
        m.fetchone = lambda: rows.pop(0) if rows else None
        return m

    conn.execute.side_effect = _ex
    with patch(
        "api_gateway.deps.fetch_prepaid_balance_list_usd", return_value=Decimal("100")
    ):
        ok, reason, meta = _evaluate_commercial_feature_access(
            conn, tenant_id="t_free", feature_name="AI_DEEP_ANALYSIS"
        )
    assert ok is False
    assert reason == "plan_feature_disabled"
    assert meta.get("plan_id") == "free"


def test_professional_plan_allows_with_balance() -> None:
    conn = MagicMock()
    rows = [
        {
            "plan_entitlement_key": "ai_deep_analysis",
            "min_prepaid_balance_list_usd": Decimal("0"),
        },
        {
            "entitlements_json": {"ai_deep_analysis": True},
            "plan_id": "professional",
        },
    ]

    def _ex(q: str, p: object) -> MagicMock:
        m = MagicMock()
        m.fetchone = lambda: rows.pop(0) if rows else None
        return m

    conn.execute.side_effect = _ex
    with patch(
        "api_gateway.deps.fetch_prepaid_balance_list_usd", return_value=Decimal("1")
    ):
        ok, reason, _meta = _evaluate_commercial_feature_access(
            conn, tenant_id="t_pro", feature_name="AI_DEEP_ANALYSIS"
        )
    assert ok is True
    assert reason == "ok"


def test_insufficient_prepaid() -> None:
    conn = MagicMock()
    rows = [
        {
            "plan_entitlement_key": "ai_deep_analysis",
            "min_prepaid_balance_list_usd": Decimal("10"),
        },
        {
            "entitlements_json": {"ai_deep_analysis": True},
            "plan_id": "professional",
        },
    ]

    def _ex(q: str, p: object) -> MagicMock:
        m = MagicMock()
        m.fetchone = lambda: rows.pop(0) if rows else None
        return m

    conn.execute.side_effect = _ex
    with patch(
        "api_gateway.deps.fetch_prepaid_balance_list_usd", return_value=Decimal("2")
    ):
        ok, reason, _m = _evaluate_commercial_feature_access(
            conn, tenant_id="t1", feature_name="AI_DEEP_ANALYSIS"
        )
    assert ok is False
    assert reason == "insufficient_prepaid"


@patch("api_gateway.deps.psycopg.connect")
@patch("api_gateway.deps.get_gateway_settings")
def test_http_layer_402_when_plan_blocks(
    mock_settings: MagicMock, mock_connect: MagicMock
) -> None:
    s = MagicMock()
    s.commercial_enabled = True
    s.commercial_entitlement_enforce = True
    s.commercial_default_tenant_id = "default"
    mock_settings.return_value = s

    conn = MagicMock()
    rows = [
        {
            "plan_entitlement_key": "ai_deep_analysis",
            "min_prepaid_balance_list_usd": Decimal("0"),
        },
        {
            "entitlements_json": {"ai_deep_analysis": False},
            "plan_id": "free",
        },
    ]

    def _ex(q: str, p: object) -> MagicMock:
        m = MagicMock()
        m.fetchone = lambda: rows.pop(0) if rows else None
        return m

    conn.execute.side_effect = _ex
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=None)
    mock_connect.return_value = ctx

    auth = GatewayAuthContext(
        actor="c",
        auth_method="gateway_jwt",
        roles=frozenset(),
        tenant_id="t_free",
    )
    with patch(
        "api_gateway.deps.fetch_prepaid_balance_list_usd", return_value=Decimal("10")
    ):
        with pytest.raises(HTTPException) as ei:
            commercial_feature_access_check_or_http(
                auth=auth, feature_name="AI_DEEP_ANALYSIS"
            )
    assert ei.value.status_code == 402
    d = ei.value.detail
    assert d["error"] == "COMMERCIAL_ENTITLEMENT_REQUIRED"
    assert d["reason"] == "plan_feature_disabled"


@patch("api_gateway.deps.psycopg.connect")
@patch("api_gateway.deps.get_gateway_settings")
def test_http_layer_ok_zahlend(
    mock_settings: MagicMock, mock_connect: MagicMock
) -> None:
    s = MagicMock()
    s.commercial_enabled = True
    s.commercial_entitlement_enforce = True
    s.commercial_default_tenant_id = "default"
    mock_settings.return_value = s
    conn = MagicMock()
    rows = [
        {
            "plan_entitlement_key": "ai_deep_analysis",
            "min_prepaid_balance_list_usd": Decimal("0"),
        },
        {
            "entitlements_json": {"ai_deep_analysis": True},
            "plan_id": "professional",
        },
    ]

    def _ex(q: str, p: object) -> MagicMock:
        m = MagicMock()
        m.fetchone = lambda: rows.pop(0) if rows else None
        return m

    conn.execute.side_effect = _ex
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=conn)
    ctx.__exit__ = MagicMock(return_value=None)
    mock_connect.return_value = ctx
    auth = GatewayAuthContext(
        actor="c",
        auth_method="gateway_jwt",
        roles=frozenset(),
        tenant_id="t_pro",
    )
    with patch(
        "api_gateway.deps.fetch_prepaid_balance_list_usd", return_value=Decimal("1")
    ):
        commercial_feature_access_check_or_http(
            auth=auth, feature_name="AI_DEEP_ANALYSIS"
        )
