import sqlite3
from pathlib import Path

import pytest
from appdb import SEED_TASTE, AppDb
from migrate import apply_migrations


def _query(path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_fresh_database_is_migrated_and_seeded(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    AppDb(path)

    assert _query(path, "PRAGMA user_version")[0][0] == 1
    assert AppDb(path).get_current_taste() == (1, SEED_TASTE)
    assert len(_query(path, "SELECT 1 FROM taste_versions")) == 1


def test_reopening_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db = AppDb(path)
    db.add_song("abc", "Title", "Artist", "u", "Verdict: YES (90% confidence)", "q", 1)

    AppDb(path)

    assert db.get_seen_ids() == {"abc"}
    assert len(_query(path, "SELECT 1 FROM taste_versions")) == 1


def test_failed_migration_rolls_back_and_keeps_version(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_ok.sql").write_text("CREATE TABLE a (id INTEGER);")
    (migrations / "0002_bad.sql").write_text("CREATE TABLE b (id INTEGER);\nINSERT INTO missing VALUES (1);")

    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations)
    conn.close()

    assert _query(path, "PRAGMA user_version")[0][0] == 1
    tables = {r["name"] for r in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"a"}


def test_migration_numbers_must_be_consecutive(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("SELECT 1;")
    (migrations / "0003_c.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_database_newer_than_code_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("PRAGMA user_version = 5")
    with pytest.raises(RuntimeError):
        apply_migrations(conn, migrations)
    conn.close()
