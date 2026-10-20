import sqlite3
from pathlib import Path

import pytest
from appdb import AppDb
from migrate import apply_migrations


def _query(path: Path, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_fresh_database_is_migrated_with_no_taste(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    AppDb(path)

    assert [r[0] for r in _query(path, "SELECT version FROM schema_migrations")] == [20261010120000, 20261020120000]
    tables = {r["name"] for r in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"songs", "taste", "schema_migrations"} <= tables
    assert AppDb(path).get_current_taste() is None


def test_artwork_migration_fills_thumbnails_for_existing_rows(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    initial = Path(__file__).parent.parent / "migrations" / "20261010120000_initial.sql"
    conn.executescript(initial.read_text())
    conn.execute("INSERT INTO songs (video_id, title, artist, url, verdict, confidence) VALUES ('abc', 't', 'a', 'u', 1, 0.9)")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20261010120000)")
    conn.commit()
    conn.close()

    songs = AppDb(path).list_songs()

    assert songs[0]["thumbnail_url"] == "https://img.youtube.com/vi/abc/hqdefault.jpg"
    assert songs[0]["album_art_url"] is None


def test_reopening_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db = AppDb(path)
    db.add_song("abc", "Title", "Artist", "u", True, 0.9, "q")

    AppDb(path)

    assert db.get_seen_ids() == {"abc"}


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_ok.sql").write_text("CREATE TABLE a (id INTEGER);")
    (migrations / "20260102000000_bad.sql").write_text("CREATE TABLE b (id INTEGER);\nINSERT INTO missing VALUES (1);")

    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations)
    conn.close()

    assert [r[0] for r in _query(path, "SELECT version FROM schema_migrations")] == [20260101000000]
    tables = {r["name"] for r in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"a", "schema_migrations"}


def test_migration_older_than_the_latest_applied_still_runs(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260102000000_b.sql").write_text("CREATE TABLE b (id INTEGER);")
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)

    (migrations / "20260101000000_a.sql").write_text("CREATE TABLE a (id INTEGER);")
    apply_migrations(conn, migrations)
    conn.close()

    versions = {r[0] for r in _query(path, "SELECT version FROM schema_migrations")}
    tables = {r["name"] for r in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert versions == {20260101000000, 20260102000000}
    assert {"a", "b"} <= tables


def test_migration_timestamps_must_be_unique(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_a.sql").write_text("SELECT 1;")
    (migrations / "20260101000000_b.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_migration_file_names_must_have_a_timestamp(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_a.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_database_with_unknown_migration_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_a.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20270101000000)")
    with pytest.raises(RuntimeError):
        apply_migrations(conn, migrations)
    conn.close()
