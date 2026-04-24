from __future__ import annotations

from contextlib import contextmanager
from unittest import mock

import pytest

from shared_py.migration_latch import (
    MigrationMismatchError,
    _format_mismatch,
    assert_repo_migrations_applied_sync,
)


def test_mismatch_error_message_includes_phrase() -> None:
    m = _format_mismatch(
        ["990_future_migration.sql", "001_base.sql"],
        head="990_future_migration.sql",
    )
    err = MigrationMismatchError(m)
    assert "Migration Mismatch" in str(err)


def test_assert_sync_fails_on_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BITGET_SKIP_MIGRATION_LATCH", "0")

    @contextmanager
    def _fake_connect(*_a: object, **_k: object) -> object:
        yield mock.MagicMock()

    with mock.patch(
        "shared_py.migration_latch.postgres_migrations_dir",
        return_value=__import__("pathlib").Path("."),
    ):
        with mock.patch(
            "shared_py.migration_latch.list_expected_migration_filenames",
            return_value=["900_pending.sql"],
        ):
            with mock.patch(
                "shared_py.migration_latch._pending_against_db",
                return_value=["900_pending.sql"],
            ):
                with mock.patch("shared_py.migration_latch.psycopg.connect", _fake_connect):
                    with pytest.raises(
                        MigrationMismatchError,
                        match="Migration Mismatch",
                    ):
                        assert_repo_migrations_applied_sync(
                            "postgresql://u:p@h:5432/d",
                        )
