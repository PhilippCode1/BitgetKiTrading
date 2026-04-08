from __future__ import annotations

from pathlib import Path

import pytest

from config.datastore_dsn import public_meta_postgres, public_meta_redis
from config.settings import BaseServiceSettings


def test_public_meta_postgres_no_password_in_output() -> None:
    m = public_meta_postgres(
        "postgresql://dbuser:hunter2@db.example.com:5432/mydb?sslmode=require"
    )
    assert m["host"] == "db.example.com"
    assert m["port"] == 5432
    assert m["dbname"] == "mydb"
    assert m["user"] == "dbuser"
    assert "hunter2" not in str(m)


def test_public_meta_redis_host_port() -> None:
    m = public_meta_redis("redis://redis.example:6380/5")
    assert m["host"] == "redis.example"
    assert m["port"] == 6380


def test_os_env_database_url_overrides_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Container-ENV muss Host-DSN aus per CONFIG_ENV_FILE geladener Datei ueberschreiben."""
    env_file = tmp_path / "conflict.env"
    env_file.write_text(
        "DATABASE_URL=postgresql://bad:bad@localhost:5999/baddb\n"
        "REDIS_URL=redis://localhost:6380/0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFIG_ENV_FILE", str(env_file))
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://good:good@postgres.internal:5432/bitget_ai",
    )
    monkeypatch.setenv("REDIS_URL", "redis://redis.internal:6379/0")

    s = BaseServiceSettings()
    assert "postgres.internal" in s.database_url
    assert "5999" not in s.database_url
    assert "redis.internal" in s.redis_url


def test_use_docker_flag_prefers_database_url_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BITGET_USE_DOCKER_DATASTORE_DSN", "true")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://u:p@localhost:5432/wrongdb",
    )
    monkeypatch.setenv(
        "DATABASE_URL_DOCKER",
        "postgresql://u:p@postgres:5432/bitget_ai",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("REDIS_URL_DOCKER", "redis://redis:6379/0")

    s = BaseServiceSettings()
    assert s.database_url == "postgresql://u:p@postgres:5432/bitget_ai"
    assert s.redis_url == "redis://redis:6379/0"
