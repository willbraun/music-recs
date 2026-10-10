import sqlite3
from pathlib import Path

import pytest
from appdb import AppDb
from taste_profile import TasteProfile


def _add_song(db: AppDb, video_id: str = "abc") -> None:
    db.add_song(video_id, "Title", "Artist", f"https://www.youtube.com/watch?v={video_id}", True, 0.9, "q")


def test_add_song_overwrites_existing_row(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    _add_song(db)
    db.add_song("abc", "New", "Artist", "u", False, 0.6, "q2")

    songs = db.list_songs()
    assert [s["title"] for s in songs] == ["New"]
    assert (songs[0]["recommended"], songs[0]["confidence"]) == (False, 0.6)
    assert db.get_seen_ids() == {"abc"}


def test_confidence_must_be_between_half_and_one(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    for confidence in (0.3, 1.2):
        with pytest.raises(sqlite3.IntegrityError):
            db.add_song("abc", "T", "A", "u", True, confidence, "q")


def test_get_current_taste_is_none_when_empty(tmp_path: Path) -> None:
    assert AppDb(tmp_path / "app.db").get_current_taste() is None


def test_save_taste_round_trips_the_profile(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    profile = TasteProfile(liked_artists=["Flume"], disliked_genres=["Country"], notes="English only.")

    saved = db.save_taste(profile)

    assert db.get_current_taste() == saved
    assert saved.profile == profile
    assert saved.updated_at


def test_saving_twice_leaves_one_row_with_the_second_profile(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db = AppDb(path)
    db.save_taste(TasteProfile(liked_genres=["Rock"]))
    db.save_taste(TasteProfile(liked_genres=["Jazz"]))

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM taste").fetchone()[0] == 1
    finally:
        conn.close()
    assert db.get_current_taste().profile.liked_genres == ["Jazz"]


def test_taste_table_rejects_a_second_row(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    AppDb(path)
    conn = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO taste (id, profile) VALUES (2, '{}')")
    finally:
        conn.close()
