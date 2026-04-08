"""Tests fuer shared_py.modul_mate_db_gates."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from shared_py.modul_mate_db_gates import fetch_tenant_modul_mate_gates
from shared_py.product_policy import (
    CustomerCommercialGates,
    demo_trading_allowed,
    live_trading_allowed,
)


def test_fetch_returns_none_when_no_row() -> None:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = None
    conn.execute.return_value = cur
    assert fetch_tenant_modul_mate_gates(conn, tenant_id="default") is None


def test_fetch_maps_row_to_gates() -> None:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = {
        "trial_active": True,
        "contract_accepted": False,
        "admin_live_trading_granted": False,
        "subscription_active": True,
        "account_paused": False,
        "account_suspended": False,
    }
    conn.execute.return_value = cur
    g = fetch_tenant_modul_mate_gates(conn, tenant_id="t1")
    assert isinstance(g, CustomerCommercialGates)
    assert g.trial_active is True
    assert demo_trading_allowed(g)
    assert not live_trading_allowed(g)


def test_fetch_rejects_non_mapping_row() -> None:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = ("x",)
    conn.execute.return_value = cur
    with pytest.raises(TypeError, match="dict_row"):
        fetch_tenant_modul_mate_gates(conn, tenant_id="t1")
