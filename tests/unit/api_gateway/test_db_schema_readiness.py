from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from api_gateway.db import check_postgres_schema_for_ready, list_expected_migration_filenames
from shared_py.postgres_migrations import migration_sort_key


def test_migration_sort_key_orders_numeric_prefix_before_lexicographic() -> None:
    paths = [
        Path("100_z.sql"),
        Path("20_a.sql"),
        Path("020_b.sql"),
    ]
    names = sorted(paths, key=migration_sort_key)
    assert [p.name for p in names] == ["020_b.sql", "20_a.sql", "100_z.sql"]


def test_list_expected_migration_filenames_respects_sort(tmp_path: Path) -> None:
    d = tmp_path / "mig"
    d.mkdir()
    (d / "020_second.sql").write_text("SELECT 1;", encoding="utf-8")
    (d / "010_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (d / "readme.txt").write_text("x", encoding="utf-8")
    with patch.dict("os.environ", {"BITGET_POSTGRES_MIGRATIONS_DIR": str(d)}, clear=False):
        names = list_expected_migration_filenames()
    assert names == ["010_first.sql", "020_second.sql"]


@pytest.mark.parametrize(
    ("payload", "exp_ok"),
    [
        ({"status": "ok"}, True),
        ({"status": "error", "missing_tables": ["app.x"], "pending_migrations_preview": []}, False),
        ({"status": "error", "pending_migrations": ["010_a.sql"]}, False),
    ],
)
def test_check_postgres_schema_for_ready(payload: dict, exp_ok: bool) -> None:
    with patch("api_gateway.db.get_db_health", return_value=payload):
        ok, detail = check_postgres_schema_for_ready()
    assert ok is exp_ok
    if exp_ok:
        assert detail == "ok"
    else:
        assert detail
