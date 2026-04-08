from __future__ import annotations

from config.bootstrap import redact_settings_dict, settings_public_snapshot
from config.settings import BaseServiceSettings


def test_redact_settings_dict_masks_secrets() -> None:
    raw = {
        "log_level": "INFO",
        "admin_token": "x",
        "jwt_secret": "y",
        "database_url": "postgresql://u:p@db.internal:5432/app",
        "nested": {"api_key": "z"},
    }
    red = redact_settings_dict(raw)
    assert red["log_level"] == "INFO"
    assert red["admin_token"] == "***"
    assert red["jwt_secret"] == "***"
    assert red["database_url"] == "postgresql://***@db.internal:5432/app"
    assert red["nested"]["api_key"] == "***"


def test_settings_public_snapshot_is_safe_subset(monkeypatch) -> None:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("EXECUTION_MODE", "paper")
    s = BaseServiceSettings()
    snap = settings_public_snapshot(s)
    assert snap["production"] is False
    assert "jwt_secret" not in snap
    assert snap["execution_mode"] == "paper"
