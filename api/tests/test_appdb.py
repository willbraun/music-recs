import sqlite3
from pathlib import Path

import numpy as np
import pytest
from appdb import AppDb
from db import connect
from taste_profile import TasteProfile

MODEL = "model/x"


def _embedding(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float32)


def _add_song(db: AppDb, video_id: str = "abc", title: str = "Title", artist: str = "Artist", **overrides) -> None:
    args = {
        "score": 0.9,
        "recommended": True,
        "query": "q",
        "embedding": _embedding(1, 0, 0),
        "model": MODEL,
        **overrides,
    }
    db.add_song(video_id, title, artist, f"https://www.youtube.com/watch?v={video_id}", **args)


@pytest.fixture
def db(tmp_path: Path) -> AppDb:
    return AppDb(tmp_path / "app.db")


def test_add_song_overwrites_existing_row(db: AppDb) -> None:
    _add_song(db)
    _add_song(db, title="New", score=0.2, recommended=False)

    songs = db.list_songs()
    assert [(s["title"], s["score"], s["recommended"]) for s in songs] == [("New", 0.2, False)]
    assert db.get_seen_ids() == {"abc"}


def test_add_song_stores_the_embedding_with_the_song(db: AppDb) -> None:
    _add_song(db)
    db.set_feedback("abc", 1)

    [(embedding, rating)] = db.get_rated_embeddings(MODEL)

    assert embedding.tolist() == [1.0, 0.0, 0.0]
    assert rating == 1


def test_embedding_round_trips_unchanged(db: AppDb) -> None:
    original = np.random.default_rng(0).normal(size=64).astype(np.float32)
    _add_song(db, embedding=original)
    db.set_feedback("abc", -1)

    [(embedding, _)] = db.get_rated_embeddings(MODEL)

    assert np.array_equal(embedding, original)


def test_rated_embeddings_skip_unrated_songs_and_other_models(db: AppDb) -> None:
    _add_song(db, "liked")
    _add_song(db, "disliked", embedding=_embedding(0, 1, 0))
    _add_song(db, "unrated")
    _add_song(db, "old_model", model="old")
    for video_id, rating in [("liked", 1), ("disliked", -1), ("old_model", 1)]:
        db.set_feedback(video_id, rating)

    ratings = [rating for _, rating in db.get_rated_embeddings(MODEL)]

    assert sorted(ratings) == [-1, 1]


def test_artist_embeddings_skip_disliked_songs_and_other_models(db: AppDb) -> None:
    _add_song(db, "unrated", artist="A")
    _add_song(db, "liked", artist="B")
    _add_song(db, "disliked", artist="C")
    _add_song(db, "old_model", artist="D", model="old")
    db.set_feedback("liked", 1)
    db.set_feedback("disliked", -1)

    artists = sorted(artist for artist, _ in db.get_artist_embeddings(MODEL))

    assert artists == ["A", "B"]


def test_feedback_rating_must_be_like_or_dislike(db: AppDb, tmp_path: Path) -> None:
    _add_song(db)
    with connect(tmp_path / "app.db") as conn:
        conn.execute("INSERT INTO feedback (video_id, rating) VALUES ('abc', -1)")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE feedback SET rating = 0")


def test_rated_song_cannot_be_deleted_or_replaced(db: AppDb, tmp_path: Path) -> None:
    _add_song(db)
    db.set_feedback("abc", 1)
    with connect(tmp_path / "app.db") as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM songs WHERE video_id = 'abc'")

    _add_song(db)  # Re-adding a rated song must not hit the foreign key.


def test_score_must_be_between_zero_and_one(db: AppDb) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _add_song(db, score=1.5)


def test_get_current_taste_is_none_when_empty(db: AppDb) -> None:
    assert db.get_current_taste() is None


def test_save_taste_twice_keeps_one_row_with_the_second_profile(db: AppDb, tmp_path: Path) -> None:
    db.save_taste(TasteProfile(liked_genres=["Rock"]))
    saved = db.save_taste(TasteProfile(liked_genres=["Jazz"], notes="n"))

    assert db.get_current_taste() == saved
    assert saved.profile.liked_genres == ["Jazz"]
    with connect(tmp_path / "app.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM taste").fetchone()[0] == 1


def test_set_feedback_upserts_and_resets_the_timestamp(db: AppDb, tmp_path: Path) -> None:
    _add_song(db)
    first = db.set_feedback("abc", 1)
    with connect(tmp_path / "app.db") as conn:
        conn.execute("UPDATE feedback SET created_at = '2000-01-01 00:00:00'")

    second = db.set_feedback("abc", -1)

    assert first is not None and second is not None
    assert second["rating"] == -1
    assert second["created_at"] > "2000-01-01 00:00:00"


def test_set_feedback_on_unknown_song_returns_none(db: AppDb) -> None:
    assert db.set_feedback("missing", 1) is None


def test_clear_feedback(db: AppDb) -> None:
    _add_song(db)
    db.set_feedback("abc", 1)

    assert db.clear_feedback("abc")
    assert db.clear_feedback("abc")  # Clearing an unrated song is fine.
    assert db.list_songs()[0]["rating"] is None
    assert not db.clear_feedback("missing")


def test_recent_likes_are_newest_first_and_only_likes(db: AppDb, tmp_path: Path) -> None:
    for video_id in ["a", "b", "c"]:
        _add_song(db, video_id, title=f"T{video_id}", artist=f"A{video_id}")
    db.set_feedback("a", 1)
    db.set_feedback("b", -1)
    db.set_feedback("c", 1)

    assert db.get_recent_likes(10) == [("Ac", "Tc"), ("Aa", "Ta")]
    assert db.get_recent_likes(1) == [("Ac", "Tc")]


def test_list_songs_filters_orders_and_pages(db: AppDb) -> None:
    _add_song(db, "a", title="Alpha", recommended=True)
    _add_song(db, "b", title="Beta", recommended=False)
    _add_song(db, "c", title="Gamma", recommended=True)

    assert [s["video_id"] for s in db.list_songs()] == ["c", "b", "a"]
    assert [s["video_id"] for s in db.list_songs(sort="oldest")] == ["a", "b", "c"]
    assert [s["video_id"] for s in db.list_songs(recommended=True)] == ["c", "a"]
    assert [s["video_id"] for s in db.list_songs(recommended=False)] == ["b"]
    assert [s["video_id"] for s in db.list_songs(limit=1, offset=1)] == ["b"]
    assert db.list_songs(limit=1, offset=5) == []
    assert db.count_songs() == 3
    assert db.count_songs(recommended=True) == 2


def test_list_songs_search_ignores_case_and_escapes_wildcards(db: AppDb) -> None:
    _add_song(db, "a", title="Kid A", artist="Radiohead")
    _add_song(db, "b", title="100% Pure", artist="Other")
    _add_song(db, "c", title="Nothing", artist="Other")

    assert [s["video_id"] for s in db.list_songs(q="RADIO")] == ["a"]
    assert [s["video_id"] for s in db.list_songs(q="%")] == ["b"]
    assert db.list_songs(q="_") == []
    assert db.count_songs(q="other") == 2


def test_list_songs_includes_rating(db: AppDb) -> None:
    _add_song(db, "a")
    _add_song(db, "b")
    db.set_feedback("a", -1)

    assert {s["video_id"]: s["rating"] for s in db.list_songs()} == {"a": -1, "b": None}
