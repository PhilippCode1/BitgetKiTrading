from __future__ import annotations

import pytest

from alert_engine.config import Settings
from alert_engine.telegram.api_client import TelegramApiClient


def test_send_message_dry_run_no_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_DRY_RUN", "true")
    s = Settings(telegram_dry_run=True, telegram_message_safe_len=3500, telegram_bot_token="")
    api = TelegramApiClient(s)
    r = api.send_message(12345, "hello " * 10)
    assert r.get("ok") is True
    assert r.get("dry_run") is True
