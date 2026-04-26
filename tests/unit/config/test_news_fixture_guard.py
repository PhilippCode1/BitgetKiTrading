from __future__ import annotations

import pytest

from config.settings import BaseServiceSettings


def test_news_fixture_mode_forbidden_when_app_env_shadow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "shadow")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "true")
    with pytest.raises(ValueError, match="NEWS_FIXTURE_MODE"):
        BaseServiceSettings()


def test_news_fixture_mode_forbidden_when_app_env_production_without_production_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "true")
    with pytest.raises(ValueError, match="NEWS_FIXTURE_MODE"):
        BaseServiceSettings()


def test_news_fixture_with_demo_allowed_only_local_like_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "true")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "true")
    s = BaseServiceSettings()
    assert s.news_fixture_mode is True
    assert s.bitget_demo_enabled is True


def test_news_fixture_and_demo_on_production_app_env_triggers_fixture_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("NEWS_FIXTURE_MODE", "true")
    monkeypatch.setenv("BITGET_DEMO_ENABLED", "true")
    with pytest.raises(ValueError, match="NEWS_FIXTURE_MODE"):
        BaseServiceSettings()
