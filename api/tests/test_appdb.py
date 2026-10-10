import sqlite3
from pathlib import Path

import pytest
from appdb import AppDb


def _add_song(db: AppDb, video_id: str = "abc", taste_version: int = 1) -> None:
    db.add_song(video_id, "Title", "Artist", f"https://www.youtube.com/watch?v={video_id}", "Verdict: YES (90% confidence)", "q", taste_version)


def test_add_song_overwrites_existing_row(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    _add_song(db)
    db.add_song("abc", "New", "Artist", "u", "Verdict: NO (60% confidence)", "q2", 1)

    songs = db.list_songs()
    assert [s["title"] for s in songs] == ["New"]
    assert db.get_seen_ids() == {"abc"}


def test_feedback_rating_must_be_like_or_dislike(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    _add_song(AppDb(path))
    conn = sqlite3.connect(path)
    try:
        conn.execute("INSERT INTO feedback (video_id, rating) VALUES ('abc', -1)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE feedback SET rating = 0")
    finally:
        conn.close()


def test_rated_song_cannot_be_deleted_or_replaced(tmp_path: Path) -> None:
    from db import connect

    path = tmp_path / "app.db"
    db = AppDb(path)
    _add_song(db)
    with connect(path) as conn:
        conn.execute("INSERT INTO feedback (video_id, rating) VALUES ('abc', 1)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM songs WHERE video_id = 'abc'")

    _add_song(db)  # Re-adding a rated song must not hit the foreign key.


def test_unknown_taste_version_is_rejected(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    with pytest.raises(sqlite3.IntegrityError):
        _add_song(db, taste_version=99)
