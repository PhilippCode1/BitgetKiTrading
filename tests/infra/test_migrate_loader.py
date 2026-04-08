from __future__ import annotations

from pathlib import Path

import pytest

from infra.migrate import MigrationError, iter_migration_sql_paths, load_migration_sql


def test_iter_migration_sql_paths_sorted_and_filters(tmp_path: Path) -> None:
    (tmp_path / "020_b.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "010_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "030_ignore.txt").write_text("x", encoding="utf-8")
    (tmp_path / "040_backup.sql~").write_bytes(b"SELECT 1;")
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "nested.sql").write_text("SELECT 1;", encoding="utf-8")

    paths = iter_migration_sql_paths(tmp_path)
    names = [p.name for p in paths]
    # Suffix .sql~ zaehlt nicht als .sql
    assert names == ["010_a.sql", "020_b.sql"]


def test_iter_migration_sql_paths_orders_by_numeric_prefix_not_lex(tmp_path: Path) -> None:
    """Unpadded 20_ muss vor 100_ laufen (nicht lexikographisch 100 vor 20)."""
    (tmp_path / "100_later.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "20_early.sql").write_text("SELECT 1;", encoding="utf-8")
    names = [p.name for p in iter_migration_sql_paths(tmp_path)]
    assert names == ["20_early.sql", "100_later.sql"]


def test_load_migration_sql_utf8_bom_ok(tmp_path: Path) -> None:
    p = tmp_path / "x.sql"
    p.write_bytes(b"\xef\xbb\xbfSELECT 1;\n")
    sql = load_migration_sql(p)
    assert sql == "SELECT 1;"


def test_load_migration_sql_rejects_nul(tmp_path: Path) -> None:
    p = tmp_path / "bad.sql"
    p.write_bytes(b"SELECT \x00 1;")
    with pytest.raises(MigrationError, match="NUL"):
        load_migration_sql(p)


def test_load_migration_sql_rejects_utf16_bom(tmp_path: Path) -> None:
    p = tmp_path / "u16.sql"
    p.write_bytes(b"\xff\xfe" + b"S\x00E\x00L\x00E\x00C\x00T\x00 \x001\x00;\x00")
    with pytest.raises(MigrationError, match="UTF-16"):
        load_migration_sql(p)


def test_load_migration_sql_rejects_empty(tmp_path: Path) -> None:
    p = tmp_path / "empty.sql"
    p.write_text("   \n\t  ", encoding="utf-8")
    with pytest.raises(MigrationError, match="leer"):
        load_migration_sql(p)
