from pathlib import Path
from types import SimpleNamespace

import embed
import numpy as np
import pipeline
import pytest
from appdb import AppDb
from fetch import Song
from huggingface_hub.errors import LocalEntryNotFoundError
from taste_profile import TasteProfile


def _song(video_id: str, tmp_path: Path, artist: str | None = None) -> Song:
    clip = tmp_path / f"{video_id}.wav"
    clip.touch()
    return Song(video_id, f"Title {video_id}", artist or f"Artist {video_id}", f"https://example.com/{video_id}", clip)


def test_find_songs_distributes_requests_across_queries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    requested: list[tuple[str, int]] = []

    def fake_fetch(query: str, count: int, skip_ids: set[str], workdir: Path, disliked_artists):
        requested.append((query, count))
        for i in range(count):
            yield _song(f"{query}{i}", tmp_path)

    monkeypatch.setattr(pipeline, "fetch_songs", fake_fetch)
    songs = pipeline._find_songs([("a", "familiar"), ("b", None)], 5, set(), tmp_path)

    first_batch = [next(songs) for _ in range(5)]

    assert requested == [("a", 3), ("b", 2)]
    assert [(s.video_id, q, t) for s, q, t in first_batch] == [
        ("a0", "a", "familiar"),
        ("a1", "a", "familiar"),
        ("a2", "a", "familiar"),
        ("b0", "b", None),
        ("b1", "b", None),
    ]


def test_find_songs_expands_batches_until_the_search_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline, "MAX_SEARCH_RESULTS_PER_QUERY", 6)
    monkeypatch.setattr(pipeline, "OVERFETCH", 3)
    counts: list[int] = []

    def fake_fetch(query: str, count: int, skip_ids: set[str], workdir: Path, disliked_artists):
        counts.append(count)
        return iter(())

    monkeypatch.setattr(pipeline, "fetch_songs", fake_fetch)

    assert list(pipeline._find_songs([("a", None)], 1, set(), tmp_path)) == []
    assert counts == [1, 2]


def test_find_songs_records_yielded_ids_as_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter([_song("x", tmp_path)]))
    skip_ids: set[str] = set()

    list(pipeline._find_songs([("a", None)], 1, skip_ids, tmp_path))

    assert "x" in skip_ids


def test_find_songs_passes_disliked_artists_to_the_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    received: list = []
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: received.append(args[4]) or iter(()))

    list(pipeline._find_songs([("a", None)], 1, set(), tmp_path, ["Nickelback"]))

    assert received[0] == ["Nickelback"]


def test_download_model_skipped_when_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert list(pipeline._download_model_if_missing("org/model")) == []
    assert calls == [(("org/model",), {"local_files_only": True})]


def test_download_model_downloads_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def fake_download(model_id: str, **kwargs) -> None:
        calls.append(kwargs)
        if kwargs.get("local_files_only"):
            raise LocalEntryNotFoundError("missing")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_download)

    assert list(pipeline._download_model_if_missing("org/model")) == [{"type": "downloading_model", "model": "org/model"}]
    assert calls == [{"local_files_only": True}, {}]


@pytest.fixture
def appdb(tmp_path: Path) -> AppDb:
    db = AppDb(tmp_path / "app.db")
    db.save_taste(TasteProfile(liked_genres=["Rock"], liked_artists=["Flume"], disliked_artists=["Nickelback"]))
    return db


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replaces the model and network layers; scores are taken per video id."""
    state = SimpleNamespace(
        found=["a", "b", "c"],
        artists={},
        seeds=[],
        seed_args=[],
        scores={},
        embedded=[],
        fetch_args=None,
        generated=[],
        scorer_args=None,
    )

    def fake_fetch_songs(query, count, skip_ids, workdir, disliked_artists=(), required_artist=None):
        state.seed_args.append((query, count, required_artist))
        skip_ids.update(state.seeds)
        for video_id in state.seeds[:count]:
            yield _song(video_id, tmp_path)

    def fake_find_songs(searches, count, skip_ids, workdir, disliked_artists):
        state.fetch_args = (searches, count, set(skip_ids), list(disliked_artists))
        for video_id in state.found:
            yield _song(video_id, tmp_path, state.artists.get(video_id)), searches[0][0], searches[0][1]

    def fake_embed_audio(clip_path: Path) -> np.ndarray:
        state.embedded.append(clip_path.stem)
        # The second value identifies the clip, so the fake scorer can tell songs apart.
        return np.array([1.0, len(state.embedded) - 1], dtype=np.float32)

    class FakeScorer:
        def score(self, embedding: np.ndarray) -> float:
            return state.scores.get(state.embedded[int(embedding[1])], 0.9)

    def fake_build_scorer(profile, rated, artist_embeddings=()):
        state.scorer_args = (profile, rated, list(artist_embeddings))
        return FakeScorer()

    def fake_generate(taste: str, exploration: int, n: int, liked_artists, recent_likes):
        state.generated.append((taste, exploration, n, list(liked_artists), list(recent_likes)))
        return [SimpleNamespace(query="generated", tier="adjacent")]

    monkeypatch.setattr(pipeline, "_find_songs", fake_find_songs)
    monkeypatch.setattr(pipeline, "fetch_songs", fake_fetch_songs)
    monkeypatch.setattr(pipeline, "_download_model_if_missing", lambda model_id: iter(()))
    monkeypatch.setattr("embed.embed_audio", fake_embed_audio)
    monkeypatch.setattr("scorer.build_scorer", fake_build_scorer)
    monkeypatch.setattr("queries.generate_queries", fake_generate)
    return state


def test_run_with_query_stops_once_count_is_recommended(appdb: AppDb, stub_pipeline) -> None:
    events = list(pipeline.run("my query", 2, 40, appdb))

    assert [e["type"] for e in events] == [
        "started",
        "seeding",
        "fetching",
        "analyzing",
        "scored",
        "analyzing",
        "scored",
        "done",
    ]
    assert events[0] == {"type": "started", "query": "my query", "count": 2, "exploration": 40}
    assert events[-1] == {"type": "done", "analyzed": 2, "recommended": 2, "count": 2}
    assert stub_pipeline.fetch_args[0] == [("my query", None)]
    assert stub_pipeline.fetch_args[1] == 2 * pipeline.CANDIDATES_PER_RECOMMENDATION
    assert [s["video_id"] for s in appdb.list_songs()] == ["b", "a"]


def test_run_passes_disliked_artists_to_the_search(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.fetch_args[3] == ["Nickelback"]


def test_run_builds_the_scorer_from_the_taste_and_rated_songs(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    profile, rated, _ = stub_pipeline.scorer_args
    assert profile.liked_genres == ["Rock"]
    assert rated == []


def test_run_scored_event_includes_score_and_recommended(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.scores["a"] = 0.2
    stub_pipeline.found = ["a"]

    scored = [e for e in pipeline.run("q", 1, 50, appdb) if e["type"] == "scored"][0]

    assert scored["recommended"] is False
    assert scored["score"] == 0.2
    assert scored["video_id"] == "a"
    assert "description" not in scored


def test_run_threshold_follows_exploration(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.scores["a"] = 0.5
    stub_pipeline.found = ["a"]

    strict = [e for e in pipeline.run("q", 1, 0, appdb) if e["type"] == "scored"][0]
    open_ = [e for e in pipeline.run("q", 1, 100, appdb) if e["type"] == "scored"][0]

    assert (strict["recommended"], open_["recommended"]) == (False, True)


def test_run_stores_every_analyzed_song_with_its_embedding(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.scores["a"] = 0.2
    stub_pipeline.found = ["a", "b"]

    list(pipeline.run("q", 1, 50, appdb))

    songs = {s["video_id"]: s for s in appdb.list_songs()}
    assert {k: (v["score"], v["recommended"]) for k, v in songs.items()} == {"a": (0.2, False), "b": (0.9, True)}
    for video_id in songs:
        appdb.set_feedback(video_id, 1)
    assert len(appdb.get_rated_embeddings(embed.MODEL_ID)) == 2


def test_run_reports_running_recommended_count(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.scores["a"] = 0.2

    analyzing = [e for e in pipeline.run("q", 2, 50, appdb) if e["type"] == "analyzing"]

    assert [(e["index"], e["recommended_count"]) for e in analyzing] == [(1, 0), (2, 0), (3, 1)]


def test_run_deletes_clips_after_embedding(appdb: AppDb, stub_pipeline, tmp_path: Path) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    assert not (tmp_path / "a.wav").exists()


def test_run_passes_seen_ids_to_the_search(appdb: AppDb, stub_pipeline) -> None:
    appdb.add_song("seen", "t", "a", "u", 0.9, True, "q", np.zeros(2, dtype=np.float32), "m")

    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.fetch_args[2] == {"seen"}


def test_run_without_query_generates_tiered_queries(appdb: AppDb, stub_pipeline) -> None:
    appdb.add_song("liked", "Liked Song", "Cherub", "u", 0.9, True, "q", np.zeros(2, dtype=np.float32), "m")
    appdb.set_feedback("liked", 1)

    events = list(pipeline.run(None, 1, 80, appdb))

    queries_event = next(e for e in events if e["type"] == "queries")
    assert queries_event["queries"] == [{"query": "generated", "tier": "adjacent"}]
    taste, exploration, n, liked_artists, recent_likes = stub_pipeline.generated[0]
    assert taste == "I like these genres: Rock. My favorite artists are Flume."
    assert (exploration, n) == (80, min(1 * pipeline.CANDIDATES_PER_RECOMMENDATION, pipeline.MAX_QUERIES))
    assert liked_artists == ["Flume"]
    assert recent_likes == [("Cherub", "Liked Song")]
    assert stub_pipeline.fetch_args[0] == [("generated", "adjacent")]
    assert next(e for e in events if e["type"] == "scored")["tier"] == "adjacent"


def test_run_finishes_with_no_songs_found(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.found = []

    events = list(pipeline.run("q", 3, 50, appdb))

    assert events[-1] == {"type": "done", "analyzed": 0, "recommended": 0, "count": 3}


def test_run_requires_a_taste(tmp_path: Path, stub_pipeline) -> None:
    with pytest.raises(ValueError, match="Set your taste first"):
        list(pipeline.run("q", 1, 50, AppDb(tmp_path / "empty.db")))


def test_run_seeds_liked_artists_without_enough_songs(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.seeds = ["s1", "s2"]

    events = list(pipeline.run("q", 1, 50, appdb))

    assert {"type": "seeding", "artist": "Flume"} in events
    assert stub_pipeline.seed_args == [("Flume", pipeline.SEED_SONGS_PER_ARTIST, "Flume")]
    assert {s["video_id"] for s in appdb.list_songs()} >= {"s1", "s2"}
    assert len(stub_pipeline.scorer_args[2]) == 2
    assert not [e for e in events if e["type"] == "scored" and e["video_id"].startswith("s")]
    assert {"s1", "s2"} <= stub_pipeline.fetch_args[2]


def test_run_scores_seed_songs_against_the_threshold(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.seeds = ["s1", "s2"]
    stub_pipeline.scores["s2"] = 0.1

    list(pipeline.run("q", 1, 50, appdb))

    songs = {s["video_id"]: s for s in appdb.list_songs()}
    assert (songs["s1"]["score"], songs["s1"]["recommended"]) == (0.9, True)
    assert (songs["s2"]["score"], songs["s2"]["recommended"]) == (0.1, False)
    assert songs["s1"]["query"] == "Artist s1"


def test_run_does_not_seed_artists_with_enough_analyzed_songs(appdb: AppDb, stub_pipeline) -> None:
    for i in range(pipeline.SEED_SONGS_PER_ARTIST):
        embedding = np.array([1.0, 0.0], dtype=np.float32)
        appdb.add_song(f"f{i}", "t", "Flume", "u", 0.9, True, "q", embedding, embed.MODEL_ID)

    events = list(pipeline.run("q", 1, 50, appdb))

    assert "seeding" not in [e["type"] for e in events]
    assert stub_pipeline.seed_args == []
    assert len(stub_pipeline.scorer_args[2]) == pipeline.SEED_SONGS_PER_ARTIST


def test_run_seeds_only_the_missing_songs(appdb: AppDb, stub_pipeline) -> None:
    appdb.add_song("f0", "t", "Flume, Other", "u", 0.9, True, "q", np.array([1.0, 0.0], dtype=np.float32), embed.MODEL_ID)

    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.seed_args == [("Flume", pipeline.SEED_SONGS_PER_ARTIST - 1, "Flume")]


def test_run_recommends_at_most_one_song_per_artist(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.found = ["a", "b", "c", "d"]
    stub_pipeline.artists = {"a": "Mac Miller", "b": "mac miller", "c": "Mac Miller, Other", "d": "Flume"}

    events = list(pipeline.run("q", 2, 50, appdb))

    scored = [e for e in events if e["type"] == "scored"]
    assert [(e["video_id"], e["recommended"]) for e in scored] == [("a", True), ("b", False), ("c", False), ("d", True)]
    assert events[-1] == {"type": "done", "analyzed": 4, "recommended": 2, "count": 2}
    stored = {s["video_id"]: s["recommended"] for s in appdb.list_songs()}
    assert stored == {"a": True, "b": False, "c": False, "d": True}
