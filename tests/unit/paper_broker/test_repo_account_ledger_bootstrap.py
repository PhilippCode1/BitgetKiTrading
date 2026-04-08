from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from paper_broker.storage.repo_accounts import bootstrap_account


def test_bootstrap_account_writes_ledger_row() -> None:
    conn = MagicMock()
    aid = bootstrap_account(conn, initial_equity=Decimal("5000"))
    assert aid is not None
    assert conn.execute.call_count >= 2
    sql_parts = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
    assert "paper.accounts" in sql_parts
    assert "paper.account_ledger" in sql_parts
