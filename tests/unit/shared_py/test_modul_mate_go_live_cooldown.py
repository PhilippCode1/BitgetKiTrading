"""Go-Live Cooldown im zentralen Execution-Gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from shared_py.modul_mate_db_gates import assert_execution_allowed
from shared_py.product_policy import ExecutionPolicyViolationError


def _gates_row(*, live_go_live_at: datetime | None = None) -> dict:
    return {
        "trial_active": False,
        "contract_accepted": True,
        "admin_live_trading_granted": True,
        "subscription_active": True,
        "account_paused": False,
        "account_suspended": False,
        "live_go_live_at": live_go_live_at,
    }


def test_live_blocked_during_go_live_cooldown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GO_LIVE_COOLDOWN_SEC", "3600")
    conn = MagicMock()
    gates_cur = MagicMock()
    contract_cur = MagicMock()
    contract_cur.fetchone.return_value = {"?column?": 1}

    def _exec(sql: str, *args: object) -> MagicMock:
        if "tenant_modul_mate_gates" in sql:
            gates_cur.fetchone.return_value = _gates_row(
                live_go_live_at=datetime.now(tz=UTC) - timedelta(minutes=5),
            )
            return gates_cur
        if "tenant_contract" in sql:
            return contract_cur
        return MagicMock()

    conn.execute.side_effect = _exec

    with pytest.raises(ExecutionPolicyViolationError) as exc:
        assert_execution_allowed(conn, tenant_id="t1", mode="LIVE")
    assert exc.value.reason == "live_go_live_cooldown_active"


def test_live_allowed_after_cooldown_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GO_LIVE_COOLDOWN_SEC", "60")
    conn = MagicMock()
    gates_cur = MagicMock()
    contract_cur = MagicMock()
    contract_cur.fetchone.return_value = {"?column?": 1}

    def _exec(sql: str, *args: object) -> MagicMock:
        if "tenant_modul_mate_gates" in sql:
            gates_cur.fetchone.return_value = _gates_row(
                live_go_live_at=datetime.now(tz=UTC) - timedelta(hours=2),
            )
            return gates_cur
        if "tenant_contract" in sql:
            return contract_cur
        return MagicMock()

    conn.execute.side_effect = _exec

    assert assert_execution_allowed(conn, tenant_id="t1", mode="LIVE") is True
