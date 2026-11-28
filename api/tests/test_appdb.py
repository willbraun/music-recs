import sqlite3
from pathlib import Path

import pytest
from appdb import AppDb
from taste_profile import TasteProfile

PROFILE_ID = 1


def test_default_path_is_in_the_configured_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MUSIC_RECS_DATA_DIR", str(tmp_path / "data"))

    AppDb()

    assert (tmp_path / "data" / "app.db").is_file()


def _add_song(db: AppDb, video_id: str = "abc") -> None:
    db.add_song(PROFILE_ID, video_id, "Title", "Artist", f"https://www.youtube.com/watch?v={video_id}", True, 0.9, "q")


def test_add_song_overwrites_existing_row(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    _add_song(db)
    db.add_song(PROFILE_ID, "abc", "New", "Artist", "u", False, 0.6, "q2")

    songs = db.list_songs(PROFILE_ID)
    assert [song["title"] for song in songs] == ["New"]
    assert (songs[0]["recommended"], songs[0]["confidence"]) == (False, 0.6)
    assert db.get_seen_ids(PROFILE_ID) == {"abc"}


def test_add_song_stores_and_lists_artwork(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    db.add_song(
        PROFILE_ID,
        "abc",
        "T",
        "A",
        "u",
        True,
        0.9,
        "q",
        thumbnail_url="thumb",
        album_art_url="art",
        album="Album",
        musicbrainz_recording_id="rec",
        musicbrainz_release_group_id="rg",
    )

    song = db.list_songs(PROFILE_ID)[0]

    assert (song["thumbnail_url"], song["album_art_url"], song["album"]) == ("thumb", "art", "Album")
    assert (song["musicbrainz_recording_id"], song["musicbrainz_release_group_id"]) == ("rec", "rg")


def test_add_song_without_artwork_lists_nulls(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    _add_song(db)

    song = db.list_songs(PROFILE_ID)[0]

    assert [song[column] for column in ("album_art_url", "album", "musicbrainz_recording_id", "musicbrainz_release_group_id")] == [None] * 4


def test_confidence_must_be_between_half_and_one(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    for confidence in (0.3, 1.2):
        with pytest.raises(sqlite3.IntegrityError):
            db.add_song(PROFILE_ID, "abc", "T", "A", "u", True, confidence, "q")


def test_get_current_taste_is_none_when_empty(tmp_path: Path) -> None:
    assert AppDb(tmp_path / "app.db").get_current_taste(PROFILE_ID) is None


def test_save_taste_round_trips_the_profile(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    profile = TasteProfile(liked_artists=["Flume"], disliked_genres=["Country"], notes="English only.")

    saved = db.save_taste(PROFILE_ID, profile)

    assert db.get_current_taste(PROFILE_ID) == saved
    assert saved.profile == profile
    assert saved.updated_at


def test_saving_twice_leaves_one_row_with_the_second_profile(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    db = AppDb(path)
    db.save_taste(PROFILE_ID, TasteProfile(liked_genres=["Rock"]))
    db.save_taste(PROFILE_ID, TasteProfile(liked_genres=["Jazz"]))

    conn = sqlite3.connect(path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM taste").fetchone()[0] == 1
    finally:
        conn.close()
    assert db.get_current_taste(PROFILE_ID).profile.liked_genres == ["Jazz"]


def test_each_profile_has_its_own_taste_and_songs(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    db.save_taste(1, TasteProfile(liked_genres=["Rock"]))
    db.save_taste(2, TasteProfile(liked_genres=["Jazz"]))
    db.add_song(1, "abc", "T", "A", "u", True, 0.9, "q")
    db.add_song(2, "abc", "T", "A", "u", False, 0.6, "q")

    assert db.get_current_taste(1).profile.liked_genres == ["Rock"]
    assert db.get_current_taste(2).profile.liked_genres == ["Jazz"]
    assert db.get_current_taste(3) is None
    assert [song["recommended"] for song in db.list_songs(1)] == [True]
    assert [song["recommended"] for song in db.list_songs(2)] == [False]
    assert db.count_songs(1) == 1
    assert db.get_seen_ids(3) == set()


def test_profiles_are_added_updated_listed_and_deleted_with_their_data(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    first = db.add_profile("Ann", "🎸")
    second = db.add_profile("Bob", "🎹")
    db.save_taste(second["id"], TasteProfile(liked_genres=["Jazz"]))
    db.add_song(second["id"], "abc", "T", "A", "u", True, 0.9, "q")

    assert db.update_profile(first["id"], "Anna", "🎤") == {"id": first["id"], "name": "Anna", "avatar": "🎤"}
    assert db.update_profile(99, "X", "🎤") is None
    assert [profile["name"] for profile in db.list_profiles()] == ["Anna", "Bob"]
    assert db.delete_profile(second["id"])
    assert not db.delete_profile(second["id"])
    assert db.get_profile(second["id"]) is None
    assert db.get_current_taste(second["id"]) is None
    assert db.count_songs(second["id"]) == 0


def test_get_recommended_artist_counts_groups_lead_artists_and_ignores_rejected_songs(tmp_path: Path) -> None:
    db = AppDb(tmp_path / "app.db")
    db.add_song(PROFILE_ID, "a", "T", "Flume", "u", True, 0.9, "q")
    db.add_song(PROFILE_ID, "b", "T", "flume, Kai", "u", True, 0.9, "q")
    db.add_song(PROFILE_ID, "c", "T", "Flume", "u", False, 0.9, "q")
    db.add_song(PROFILE_ID, "d", "T", "Muse", "u", True, 0.9, "q")

    assert db.get_recommended_artist_counts(PROFILE_ID, 100) == {"flume": 2, "Muse": 1}
    assert db.get_recommended_artist_counts(PROFILE_ID, 2) == {"Muse": 1, "flume": 1}
