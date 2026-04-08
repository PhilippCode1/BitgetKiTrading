from __future__ import annotations

from unittest.mock import MagicMock

from learning_engine.storage.repo_processed import already_processed, mark_processed


def test_already_processed_and_mark() -> None:
    conn = MagicMock()
    cur = MagicMock()
    cur.fetchone.return_value = None
    conn.execute.return_value = cur
    assert not already_processed(conn, "events:trade_closed", "1-0")

    mark_processed(conn, "events:trade_closed", "1-0")
    assert conn.execute.call_count >= 1
