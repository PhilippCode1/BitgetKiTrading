"""Tests fuer shared_py.modul_mate_db_gates."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from shared_py.modul_mate_db_gates import (
    assert_m604_table_and_policies,
    fetch_tenant_modul_mate_gates,
)
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


def _seed_604() -> dict[str, bool | object]:
    return {
        "trial_active": False,
        "contract_accepted": True,
        "admin_live_trading_granted": False,
        "subscription_active": True,
        "account_paused": False,
        "account_suspended": False,
    }


@patch("shared_py.modul_mate_db_gates.psycopg.connect")
def test_assert_m604_ok_default_tenant(mock_connect: MagicMock) -> None:
    to_reg = MagicMock()
    to_reg.fetchone.return_value = {"t": 1}
    gates = MagicMock()
    gates.fetchone.return_value = _seed_604()

    def _exec(sql: str, *args: object) -> MagicMock:  # noqa: ARG001
        if "to_regclass" in (sql or ""):
            return to_reg
        if "FROM app.tenant_modul_mate_gates" in (sql or ""):
            return gates
        return MagicMock()

    conn = MagicMock()
    conn.execute.side_effect = _exec
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = None
    mock_connect.return_value = cm

    g = assert_m604_table_and_policies("postgresql://x", tenant_id="default")
    assert g.contract_accepted is True
    assert demo_trading_allowed(g) is True


@patch("shared_py.modul_mate_db_gates.psycopg.connect")
def test_assert_m604_missing_table(mock_connect: MagicMock) -> None:
    to_reg = MagicMock()
    to_reg.fetchone.return_value = {"t": None}
    cm = MagicMock()
    mock_conn = MagicMock()
    mock_conn.execute.return_value = to_reg
    cm.__enter__.return_value = mock_conn
    cm.__exit__.return_value = None
    mock_connect.return_value = cm

    with pytest.raises(RuntimeError, match="to_regclass NULL"):
        assert_m604_table_and_policies("postgresql://x", tenant_id="default")
