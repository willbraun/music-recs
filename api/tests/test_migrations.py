import sqlite3
from pathlib import Path

import pytest
from appdb import AppDb
from migrate import MIGRATIONS_DIR, apply_migrations

PROFILE_ID = 1


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

    assert [row[0] for row in _query(path, "SELECT version FROM schema_migrations")] == [20261010120000, 20261020120000, 20261128120000]
    tables = {row["name"] for row in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"songs", "taste", "profiles", "schema_migrations"} <= tables
    assert AppDb(path).get_current_taste(PROFILE_ID) is None


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

    songs = AppDb(path).list_songs(0)

    assert songs[0]["thumbnail_url"] == "https://img.youtube.com/vi/abc/hqdefault.jpg"
    assert songs[0]["album_art_url"] is None


def test_reopening_is_a_no_op(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db = AppDb(path)
    db.add_song(PROFILE_ID, "abc", "Title", "Artist", "u", True, 0.9, "q")

    AppDb(path)

    assert db.get_seen_ids(PROFILE_ID) == {"abc"}


def test_new_migration_applies_to_existing_database_and_keeps_data(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_create.sql").write_text("CREATE TABLE songs (id INTEGER PRIMARY KEY, name TEXT);")
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)
    conn.execute("INSERT INTO songs (name) VALUES ('kept')")
    conn.commit()
    conn.close()

    (migrations / "20260102000000_add_column.sql").write_text("ALTER TABLE songs ADD COLUMN year INTEGER DEFAULT 2026;")
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)
    conn.close()

    assert [row[0] for row in _query(path, "SELECT version FROM schema_migrations ORDER BY version")] == [
        20260101000000,
        20260102000000,
    ]
    rows = _query(path, "SELECT name, year FROM songs")
    assert [(row["name"], row["year"]) for row in rows] == [("kept", 2026)]


def test_failed_migration_rolls_back_and_is_not_recorded(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_ok.sql").write_text("CREATE TABLE artists (id INTEGER);")
    (migrations / "20260102000000_bad.sql").write_text("CREATE TABLE albums (id INTEGER);\nINSERT INTO missing VALUES (1);")

    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations)
    conn.close()

    assert [row[0] for row in _query(path, "SELECT version FROM schema_migrations")] == [20260101000000]
    tables = {row["name"] for row in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"artists", "schema_migrations"}


def test_migration_older_than_the_latest_applied_still_runs(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260102000000_albums.sql").write_text("CREATE TABLE albums (id INTEGER);")
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)

    (migrations / "20260101000000_artists.sql").write_text("CREATE TABLE artists (id INTEGER);")
    apply_migrations(conn, migrations)
    conn.close()

    versions = {row[0] for row in _query(path, "SELECT version FROM schema_migrations")}
    tables = {row["name"] for row in _query(path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert versions == {20260101000000, 20260102000000}
    assert {"artists", "albums"} <= tables


def test_migration_timestamps_must_be_unique(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_first.sql").write_text("SELECT 1;")
    (migrations / "20260101000000_second.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_migration_file_names_must_have_a_timestamp(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "0001_first.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    with pytest.raises(ValueError):
        apply_migrations(conn, migrations)
    conn.close()


def test_database_with_unknown_migration_is_rejected(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_first.sql").write_text("SELECT 1;")

    conn = sqlite3.connect(tmp_path / "x.db")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20270101000000)")
    with pytest.raises(RuntimeError):
        apply_migrations(conn, migrations)
    conn.close()


def _read_schema(path: Path) -> list[tuple[str, str, str]]:
    rows = _query(path, "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name")
    return [(row["type"], row["name"], row["sql"]) for row in rows]


def test_applying_all_migrations_at_once_matches_upgrading_one_at_a_time(tmp_path: Path) -> None:
    all_at_once = tmp_path / "all.db"
    conn = sqlite3.connect(all_at_once)
    apply_migrations(conn)
    conn.close()

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    one_at_a_time = tmp_path / "step.db"
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        (migrations / migration.name).write_text(migration.read_text())
        conn = sqlite3.connect(one_at_a_time)
        apply_migrations(conn, migrations)
        conn.close()

    assert _read_schema(one_at_a_time) == _read_schema(all_at_once)


def test_fixed_migration_applies_after_a_failure_and_keeps_earlier_data(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260101000000_create.sql").write_text("CREATE TABLE songs (id INTEGER PRIMARY KEY, name TEXT);")
    broken = migrations / "20260102000000_add_column.sql"
    
    # Migration for a missing table, which will fail initially
    broken.write_text("ALTER TABLE missing ADD COLUMN year INTEGER;")
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    with pytest.raises(sqlite3.OperationalError):
        apply_migrations(conn, migrations)
    conn.execute("INSERT INTO songs (name) VALUES ('kept')")
    conn.commit()
    conn.close()

    # Fix the broken migration so it can be applied successfully
    broken.write_text("ALTER TABLE songs ADD COLUMN year INTEGER DEFAULT 2026;")
    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)
    conn.close()

    versions = [row[0] for row in _query(path, "SELECT version FROM schema_migrations ORDER BY version")]
    rows = _query(path, "SELECT name, year FROM songs")
    assert versions == [20260101000000, 20260102000000]
    assert [(row["name"], row["year"]) for row in rows] == [("kept", 2026)]


def test_several_pending_migrations_apply_in_timestamp_order(tmp_path: Path) -> None:
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "20260103000000_index_year.sql").write_text("CREATE INDEX songs_year ON songs (year);")
    (migrations / "20260102000000_add_year.sql").write_text("ALTER TABLE songs ADD COLUMN year INTEGER;")
    (migrations / "20260101000000_create.sql").write_text("CREATE TABLE songs (id INTEGER PRIMARY KEY);")
    path = tmp_path / "x.db"

    conn = sqlite3.connect(path)
    apply_migrations(conn, migrations)
    conn.close()

    versions = [row[0] for row in _query(path, "SELECT version FROM schema_migrations ORDER BY version")]
    indexes = {row["name"] for row in _query(path, "SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert versions == [20260101000000, 20260102000000, 20260103000000]
    assert "songs_year" in indexes


def test_first_profile_adopts_songs_and_taste_from_before_profiles(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    conn.executescript((MIGRATIONS_DIR / "20261010120000_initial.sql").read_text())
    conn.execute("INSERT INTO songs (video_id, title, artist, url, verdict, confidence) VALUES ('abc', 't', 'a', 'u', 1, 0.9)")
    conn.execute("INSERT INTO taste (id, profile) VALUES (1, '{\"liked_genres\": [\"rock\"]}')")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20261010120000)")
    conn.commit()
    conn.close()

    db = AppDb(path)
    assert db.list_profiles() == []
    profile = db.add_profile("Ann", "🎸")
    later = db.add_profile("Bob", "🎹")

    assert [song["video_id"] for song in db.list_songs(profile["id"])] == ["abc"]
    assert db.get_current_taste(profile["id"]).profile.liked_genres == ["rock"]
    assert db.list_songs(later["id"]) == []
    assert db.get_current_taste(later["id"]) is None


def test_taste_survives_upgrading_from_the_initial_version(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    conn.executescript((MIGRATIONS_DIR / "20261010120000_initial.sql").read_text())
    conn.execute("INSERT INTO taste (id, profile) VALUES (1, '{\"liked_genres\": [\"rock\"]}')")
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20261010120000)")
    conn.commit()
    conn.close()

    AppDb(path)

    rows = _query(path, "SELECT profile_id, profile FROM taste")
    assert [(row["profile_id"], row["profile"]) for row in rows] == [(0, '{"liked_genres": ["rock"]}')]


def test_migrating_enables_wal_journal_mode(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    apply_migrations(conn)
    conn.close()

    assert _query(path, "PRAGMA journal_mode")[0][0] == "wal"


def test_app_db_rejects_a_database_from_a_newer_version(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_migrations VALUES (20990101000000)")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError):
        AppDb(path)
