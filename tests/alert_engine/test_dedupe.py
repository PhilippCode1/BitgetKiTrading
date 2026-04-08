from __future__ import annotations

from unittest.mock import MagicMock

from alert_engine.alerts.dedupe import should_send_with_dedupe


def test_no_key_always_true() -> None:
    repo = MagicMock()
    assert should_send_with_dedupe(repo, None, 10) is True
    repo.try_acquire.assert_not_called()


def test_key_calls_repo() -> None:
    repo = MagicMock()
    repo.try_acquire.return_value = True
    assert should_send_with_dedupe(repo, "k1", 5) is True
    repo.try_acquire.assert_called_once_with("k1", 5)
