from pathlib import Path
from types import SimpleNamespace

import pipeline
import pytest
from analyze import Verdict
from appdb import AppDb
from artwork import SongArtwork
from fetch import Song
from huggingface_hub.errors import LocalEntryNotFoundError
from taste_profile import TasteProfile


def _song(video_id: str, tmp_path: Path, artist: str | None = None) -> Song:
    clip = tmp_path / f"{video_id}.wav"
    clip.touch()
    return Song(video_id, f"Title {video_id}", artist or f"Artist {video_id}", f"https://example.com/{video_id}", clip)


def test_find_songs_distributes_requests_across_queries(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    requested: list[tuple[str, int]] = []

    def fake_fetch(query: str, count: int, skip_ids: set[str], workdir: Path):
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

    def fake_fetch(query: str, count: int, skip_ids: set[str], workdir: Path):
        counts.append(count)
        return iter(())

    monkeypatch.setattr(pipeline, "fetch_songs", fake_fetch)

    assert list(pipeline._find_songs([("a", None)], 1, set(), tmp_path)) == []
    assert counts == [1, 2]


def test_find_songs_skips_repeat_artists_and_deletes_their_clips(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = [
        _song("a", tmp_path, "Flume"),
        _song("b", tmp_path, " flume "),
        _song("c", tmp_path, "Tame Impala"),
        _song("d", tmp_path, "Flume, Kai"),
    ]
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter(fetched))

    found = list(pipeline._find_songs([("a", None)], 3, set(), tmp_path))

    assert [s.video_id for s, _, _ in found] == ["a", "c"]
    assert not fetched[1].clip_path.exists()
    assert not fetched[3].clip_path.exists()


def test_find_songs_defers_avoided_artists_to_the_end(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # A limit of one song makes this a single batch.
    monkeypatch.setattr(pipeline, "MAX_SEARCH_RESULTS_PER_QUERY", 3)
    monkeypatch.setattr(pipeline, "OVERFETCH", 3)
    fetched = [_song("a", tmp_path, "Flume"), _song("b", tmp_path, "Muse")]
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter(fetched))

    found = list(pipeline._find_songs([("a", None)], 1, set(), tmp_path, {"flume"}))

    assert [s.video_id for s, _, _ in found] == ["b", "a"]
    assert fetched[0].clip_path.exists()


def test_find_songs_never_yields_blocked_artists_and_deletes_their_clips(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fetched = [
        _song("a", tmp_path, "Flume"),
        _song("b", tmp_path, "Muse, FLUME"),
        _song("c", tmp_path, "Tyler, The Creator"),
        _song("d", tmp_path, "Tame Impala"),
    ]
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter(fetched))
    skip_ids: set[str] = set()

    found = list(pipeline._find_songs([("a", None)], 4, skip_ids, tmp_path, blocked_artists={"flume", "tyler, the creator"}))

    assert [s.video_id for s, _, _ in found] == ["d"]
    assert not any(song.clip_path.exists() for song in fetched[:3])
    assert {"a", "b", "c"} <= skip_ids


def test_find_songs_records_yielded_ids_as_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter([_song("x", tmp_path)]))
    skip_ids: set[str] = set()

    list(pipeline._find_songs([("a", None)], 1, skip_ids, tmp_path))

    assert "x" in skip_ids


def test_download_missing_models_skips_cached_models(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert list(pipeline._download_missing_models(["org/a", "org/b"])) == []
    assert calls == [(("org/a",), {"local_files_only": True}), (("org/b",), {"local_files_only": True})]


def _fake_hub(monkeypatch: pytest.MonkeyPatch, cached: set[str], sizes: dict[str, int]) -> list[tuple[str, str]]:
    """Replaces snapshot_download; returns the (model, action) calls in order."""
    calls: list[tuple[str, str]] = []

    def fake_download(model_id: str, local_files_only: bool = False, dry_run: bool = False, tqdm_class=None):
        if local_files_only:
            calls.append((model_id, "check"))
            if model_id not in cached:
                raise LocalEntryNotFoundError("missing")
            return "path"
        if dry_run:
            calls.append((model_id, "size"))
            return [SimpleNamespace(file_size=sizes[model_id], will_download=True)]
        calls.append((model_id, "download"))
        return "path"

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_download)
    monkeypatch.setattr("model_download.POLL_SECONDS", 0.01)
    return calls


def test_download_missing_models_downloads_one_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_hub(monkeypatch, set(), {"org/model": 300})

    events = list(pipeline._download_missing_models(["org/model"]))

    assert events[0] == {"type": "downloading_models", "models": [{"model": "org/model", "total_bytes": 300}]}
    assert events[1] == {"type": "downloading_model", "model": "org/model", "total_bytes": 300}
    assert events[-2] == {
        "type": "download_progress",
        "model": "org/model",
        "downloaded_bytes": 300,
        "total_bytes": 300,
        "bytes_per_second": 0.0,
        "seconds_remaining": 0.0,
    }
    assert events[-1] == {"type": "model_downloaded", "model": "org/model"}
    assert calls == [("org/model", "check"), ("org/model", "size"), ("org/model", "download")]


def test_download_missing_models_checks_all_first_then_downloads_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _fake_hub(monkeypatch, {"org/cached"}, {"org/a": 10, "org/b": 20})

    events = list(pipeline._download_missing_models(["org/a", "org/cached", "org/b"]))

    assert events[0] == {
        "type": "downloading_models",
        "models": [{"model": "org/a", "total_bytes": 10}, {"model": "org/b", "total_bytes": 20}],
    }
    assert [(e["type"], e["model"]) for e in events if e["type"] != "download_progress" and e["type"] != "downloading_models"] == [
        ("downloading_model", "org/a"),
        ("model_downloaded", "org/a"),
        ("downloading_model", "org/b"),
        ("model_downloaded", "org/b"),
    ]
    assert calls == [
        ("org/a", "check"),
        ("org/cached", "check"),
        ("org/b", "check"),
        ("org/a", "size"),
        ("org/b", "size"),
        ("org/a", "download"),
        ("org/b", "download"),
    ]


@pytest.fixture
def appdb(tmp_path: Path) -> AppDb:
    db = AppDb(tmp_path / "app.db")
    db.save_taste(TasteProfile(liked_genres=["Rock"], liked_artists=["Flume"]))
    return db


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replaces the model and network layers; verdicts are taken per video id."""
    state = SimpleNamespace(
        found=["a", "b", "c"], verdicts={}, analyzed=[], fetch_args=None, generated=[], artwork_calls=[], required_models=[]
    )

    def fake_find_songs(searches, count, skip_ids, workdir, avoid_artists=frozenset(), blocked_artists=frozenset()):
        state.avoid_artists = avoid_artists
        state.blocked_artists = blocked_artists
        state.fetch_args = (searches, count, set(skip_ids))
        for video_id in state.found:
            yield _song(video_id, tmp_path), searches[0][0], searches[0][1]

    def fake_analyze(clip_path: Path, taste: str, exploration: int) -> Verdict:
        state.analyzed.append((clip_path.stem, taste, exploration))
        return state.verdicts.get(clip_path.stem, Verdict(True, 0.9))

    def fake_generate(taste: str, liked_artists: list[str], exploration: int, n: int, avoid_artists: list[str]):
        state.generated.append((taste, liked_artists, exploration, n))
        state.avoided = avoid_artists
        return [SimpleNamespace(query="generated", tier="adjacent")]

    def fake_find_artwork(video_id: str, artist: str, title: str) -> SongArtwork:
        state.artwork_calls.append(video_id)
        return SongArtwork(
            f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg", f"art-{video_id}", f"Album {video_id}", f"rec-{video_id}", f"rg-{video_id}"
        )

    monkeypatch.setattr(pipeline, "_find_songs", fake_find_songs)
    monkeypatch.setattr(pipeline, "find_artwork", fake_find_artwork)
    def fake_download_missing_models(model_ids: list[str]):
        state.required_models = model_ids
        return iter(())

    monkeypatch.setattr(pipeline, "_download_missing_models", fake_download_missing_models)
    monkeypatch.setattr("analyze.analyze", fake_analyze)
    monkeypatch.setattr("queries.generate_queries", fake_generate)
    return state


def test_run_with_query_stops_once_count_is_recommended(appdb: AppDb, stub_pipeline) -> None:
    events = list(pipeline.run("my query", 2, 40, appdb))

    assert [e["type"] for e in events] == ["started", "fetching", "analyzing", "scored", "analyzing", "scored", "done"]
    assert events[0] == {"type": "started", "query": "my query", "count": 2, "exploration": 40}
    assert events[-1] == {"type": "done", "analyzed": 2, "recommended": 2, "count": 2}
    assert stub_pipeline.fetch_args[0] == [("my query", None)]
    assert stub_pipeline.fetch_args[1] == 2 * pipeline.CANDIDATES_PER_RECOMMENDATION
    assert [s["video_id"] for s in appdb.list_songs()] == ["b", "a"]


def test_run_scored_event_includes_verdict_and_confidence(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = Verdict(False, 0.7)
    stub_pipeline.found = ["a"]

    scored = [e for e in pipeline.run("q", 1, 50, appdb) if e["type"] == "scored"][0]

    assert scored["recommended"] is False
    assert scored["confidence"] == 0.7
    assert scored["video_id"] == "a"
    assert "description" not in scored


def test_run_stores_artwork_and_reports_it_on_scored_events(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.found = ["a"]

    events = list(pipeline.run("q", 1, 50, appdb))

    analyzing = [e for e in events if e["type"] == "analyzing"][0]
    scored = [e for e in events if e["type"] == "scored"][0]
    assert analyzing["thumbnail_url"] == "https://img.youtube.com/vi/a/hqdefault.jpg"
    assert analyzing["album_art_url"] == "art-a"
    assert (scored["thumbnail_url"], scored["album_art_url"], scored["album"]) == (
        "https://img.youtube.com/vi/a/hqdefault.jpg",
        "art-a",
        "Album a",
    )
    assert (scored["musicbrainz_recording_id"], scored["musicbrainz_release_group_id"]) == ("rec-a", "rg-a")
    stored = appdb.list_songs()[0]
    assert (stored["thumbnail_url"], stored["album_art_url"], stored["album"]) == (
        scored["thumbnail_url"],
        "art-a",
        "Album a",
    )
    assert (stored["musicbrainz_recording_id"], stored["musicbrainz_release_group_id"]) == ("rec-a", "rg-a")


def test_run_looks_up_artwork_for_every_song(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = Verdict(False, 0.7)
    stub_pipeline.found = ["a", "b"]

    scored = {e["video_id"]: e for e in pipeline.run("q", 1, 50, appdb) if e["type"] == "scored"}

    assert stub_pipeline.artwork_calls == ["a", "b"]
    assert scored["a"]["album_art_url"] == "art-a"
    assert scored["a"]["album"] == "Album a"
    assert appdb.list_songs()[1]["album_art_url"] == "art-a"


def test_run_reports_running_recommended_count(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = Verdict(False, 0.7)

    analyzing = [e for e in pipeline.run("q", 2, 50, appdb) if e["type"] == "analyzing"]

    assert [(e["index"], e["recommended_count"]) for e in analyzing] == [(1, 0), (2, 0), (3, 1)]


def test_run_stores_not_recommended_songs(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = Verdict(False, 0.7)
    stub_pipeline.found = ["a", "b"]

    list(pipeline.run("q", 1, 50, appdb))

    stored = {s["video_id"]: (s["recommended"], s["confidence"]) for s in appdb.list_songs()}
    assert stored == {"a": (False, 0.7), "b": (True, 0.9)}


def test_run_deletes_clips_after_analysis(appdb: AppDb, stub_pipeline, tmp_path: Path) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    assert not (tmp_path / "a.wav").exists()


def test_run_passes_seen_ids_to_the_search(appdb: AppDb, stub_pipeline) -> None:
    appdb.add_song("seen", "t", "a", "u", True, 0.9, "q")

    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.fetch_args[2] == {"seen"}


def test_run_without_query_generates_tiered_queries(appdb: AppDb, stub_pipeline) -> None:
    events = list(pipeline.run(None, 1, 80, appdb))

    queries_event = next(e for e in events if e["type"] == "queries")
    assert queries_event["queries"] == [{"query": "generated", "tier": "adjacent"}]
    taste_text = "I like these genres: Rock. My favorite artists are Flume."
    assert stub_pipeline.generated == [
        (taste_text, ["Flume"], 80, min(1 * pipeline.CANDIDATES_PER_RECOMMENDATION, pipeline.MAX_QUERIES))
    ]
    assert stub_pipeline.fetch_args[0] == [("generated", "adjacent")]
    assert next(e for e in events if e["type"] == "scored")["tier"] == "adjacent"


def test_run_requires_only_the_analysis_model_when_a_query_is_given(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.required_models == ["nvidia/music-flamingo-2601-hf"]


def test_run_requires_both_models_without_a_query(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run(None, 1, 50, appdb))

    assert stub_pipeline.required_models == ["Qwen/Qwen2.5-3B-Instruct", "nvidia/music-flamingo-2601-hf"]


def test_run_downloads_models_before_searching(appdb: AppDb, stub_pipeline, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pipeline, "_download_missing_models", lambda model_ids: iter([{"type": "downloading_models", "models": []}])
    )

    types = [e["type"] for e in pipeline.run(None, 1, 50, appdb)]

    assert types[:4] == ["started", "downloading_models", "queries", "fetching"]


def test_run_passes_exploration_to_the_analyzer(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run("q", 1, 77, appdb))

    assert stub_pipeline.analyzed[0] == ("a", "I like these genres: Rock. My favorite artists are Flume.", 77)


def test_run_without_a_saved_taste_raises(tmp_path: Path, stub_pipeline) -> None:
    with pytest.raises(RuntimeError, match="Set your taste first"):
        list(pipeline.run("q", 1, 50, AppDb(tmp_path / "empty.db")))


def test_run_finishes_with_no_songs_found(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.found = []

    events = list(pipeline.run("q", 3, 50, appdb))

    assert events[-1] == {"type": "done", "analyzed": 0, "recommended": 0, "count": 3}


def test_run_avoids_artists_recommended_often(appdb: AppDb, stub_pipeline) -> None:
    for i in range(pipeline.FREQUENT_ARTIST_RECOMMENDATIONS):
        appdb.add_song(f"f{i}", "t", "Flume", "u", True, 0.9, "q")
    appdb.add_song("m", "t", "Muse", "u", True, 0.9, "q")

    list(pipeline.run(None, 1, 50, appdb))

    assert stub_pipeline.avoided == ["Flume"]
    assert stub_pipeline.avoid_artists == {"flume"}


def test_run_blocks_disliked_artists(appdb: AppDb, stub_pipeline) -> None:
    appdb.save_taste(TasteProfile(liked_genres=["Rock"], disliked_artists=["Muse", " Radiohead "]))

    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.blocked_artists == {"muse", "radiohead"}
