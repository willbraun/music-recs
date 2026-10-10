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


def _versions(path: Path) -> list[int]:
    return [r[0] for r in _query(path, "SELECT version FROM schema_migrations ORDER BY version")]


def _app_tables(path: Path) -> set[str]:
    rows = _query(path, "SELECT name FROM sqlite_master WHERE type = 'table' AND name != 'schema_migrations'")
    return {r["name"] for r in rows}


def test_fresh_database_is_migrated_and_seeded(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    AppDb(path)

    assert _versions(path) == [20261010120000]
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
    (migrations / "20260101000000_ok.sql").write_text("CREATE TABLE a (id INTEGER);")
    (migrations / "20260102000000_bad.sql").write_text("CREATE TABLE b (id INTEGER);\nINSERT INTO missing VALUES (1);")

    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations)
    conn.close()

    assert _versions(path) == [20260101000000]
    assert _app_tables(path) == {"a"}


def test_migration_timestamps_must_be_unique(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_a.sql").write_text("SELECT 1;")
    (migrations / "20260101000000_b.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_migration_file_names_must_be_timestamped(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_only_unapplied_migrations_run(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_a.sql").write_text("CREATE TABLE a (id INTEGER);")
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)
    (migrations / "20260201000000_b.sql").write_text("CREATE TABLE b (id INTEGER);")

    apply_migrations(conn, migrations)
    conn.close()

    assert _versions(path) == [20260101000000, 20260201000000]
    assert _app_tables(path) == {"a", "b"}


def test_database_with_unknown_migration_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_a.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20260201000000)")
    conn.commit()
    with pytest.raises(RuntimeError):
        apply_migrations(conn, migrations)
    conn.close()
