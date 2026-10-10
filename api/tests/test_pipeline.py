from pathlib import Path
from types import SimpleNamespace

import pipeline
import pytest
from appdb import AppDb
from fetch import Song
from huggingface_hub.errors import LocalEntryNotFoundError


def _song(video_id: str, tmp_path: Path) -> Song:
    clip = tmp_path / f"{video_id}.wav"
    clip.touch()
    return Song(video_id, f"Title {video_id}", "Artist", f"https://example.com/{video_id}", clip)


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


def test_find_songs_records_yielded_ids_as_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pipeline, "fetch_songs", lambda *args: iter([_song("x", tmp_path)]))
    skip_ids: set[str] = set()

    list(pipeline._find_songs([("a", None)], 1, skip_ids, tmp_path))

    assert "x" in skip_ids


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
    return AppDb(tmp_path / "app.db")


@pytest.fixture
def stub_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Replaces the model and network layers; verdicts are taken per video id."""
    state = SimpleNamespace(found=["a", "b", "c"], verdicts={}, analyzed=[], fetch_args=None, generated=[])

    def fake_find_songs(searches, count, skip_ids, workdir):
        state.fetch_args = (searches, count, set(skip_ids))
        for video_id in state.found:
            yield _song(video_id, tmp_path), searches[0][0], searches[0][1]

    def fake_analyze(clip_path: Path, taste: str, exploration: int) -> str:
        state.analyzed.append((clip_path.stem, exploration))
        return state.verdicts.get(clip_path.stem, "Verdict: YES (90% confidence)")

    def fake_generate(taste: str, exploration: int, n: int):
        state.generated.append((exploration, n))
        return [SimpleNamespace(query="generated", tier="adjacent")]

    monkeypatch.setattr(pipeline, "_find_songs", fake_find_songs)
    monkeypatch.setattr(pipeline, "_download_model_if_missing", lambda model_id: iter(()))
    monkeypatch.setattr("analyze.analyze", fake_analyze)
    monkeypatch.setattr("queries.generate_queries", fake_generate)
    return state


def test_run_with_query_stops_once_count_is_recommended(appdb: AppDb, stub_pipeline) -> None:
    events = list(pipeline.run("my query", 2, 40, appdb))

    assert [e["type"] for e in events] == ["started", "fetching", "analyzing", "scored", "analyzing", "scored", "done"]
    assert events[0] == {"type": "started", "query": "my query", "count": 2, "exploration": 40, "taste_version": 1}
    assert events[-1] == {"type": "done", "analyzed": 2, "recommended": 2, "count": 2}
    assert stub_pipeline.fetch_args[0] == [("my query", None)]
    assert stub_pipeline.fetch_args[1] == 2 * pipeline.CANDIDATES_PER_RECOMMENDATION
    assert [s["video_id"] for s in appdb.list_songs()] == ["b", "a"]


def test_run_scored_event_includes_description_and_verdict(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = "Verdict: NO (70% confidence)"
    stub_pipeline.found = ["a"]

    scored = [e for e in pipeline.run("q", 1, 50, appdb) if e["type"] == "scored"][0]

    assert scored["recommended"] is False
    assert scored["description"] == "Verdict: NO (70% confidence)"
    assert scored["video_id"] == "a"


def test_run_reports_running_recommended_count(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = "Verdict: NO (70% confidence)"

    analyzing = [e for e in pipeline.run("q", 2, 50, appdb) if e["type"] == "analyzing"]

    assert [(e["index"], e["recommended_count"]) for e in analyzing] == [(1, 0), (2, 0), (3, 1)]


def test_run_drops_analyses_without_a_verdict(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.verdicts["a"] = "unparseable"
    stub_pipeline.found = ["a", "b"]

    events = list(pipeline.run("q", 1, 50, appdb))

    assert [e["video_id"] for e in events if e["type"] == "scored"] == ["b"]
    assert appdb.get_seen_ids() == {"b"}
    assert events[-1]["analyzed"] == 2


def test_run_deletes_clips_after_analysis(appdb: AppDb, stub_pipeline, tmp_path: Path) -> None:
    list(pipeline.run("q", 1, 50, appdb))

    assert not (tmp_path / "a.wav").exists()


def test_run_passes_seen_ids_to_the_search(appdb: AppDb, stub_pipeline) -> None:
    appdb.add_song("seen", "t", "a", "u", "Verdict: YES (90% confidence)", "q", 1)

    list(pipeline.run("q", 1, 50, appdb))

    assert stub_pipeline.fetch_args[2] == {"seen"}


def test_run_without_query_generates_tiered_queries(appdb: AppDb, stub_pipeline) -> None:
    events = list(pipeline.run(None, 1, 80, appdb))

    queries_event = next(e for e in events if e["type"] == "queries")
    assert queries_event["queries"] == [{"query": "generated", "tier": "adjacent"}]
    assert stub_pipeline.generated == [(80, min(1 * pipeline.CANDIDATES_PER_RECOMMENDATION, pipeline.MAX_QUERIES))]
    assert stub_pipeline.fetch_args[0] == [("generated", "adjacent")]
    assert next(e for e in events if e["type"] == "scored")["tier"] == "adjacent"


def test_run_passes_exploration_to_the_analyzer(appdb: AppDb, stub_pipeline) -> None:
    list(pipeline.run("q", 1, 77, appdb))

    assert stub_pipeline.analyzed[0] == ("a", 77)


def test_run_finishes_with_no_songs_found(appdb: AppDb, stub_pipeline) -> None:
    stub_pipeline.found = []

    events = list(pipeline.run("q", 3, 50, appdb))

    assert events[-1] == {"type": "done", "analyzed": 0, "recommended": 0, "count": 3}
