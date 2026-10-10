import json
import queue
import threading
from pathlib import Path

import numpy as np
import pytest
from appdb import AppDb
from fastapi.testclient import TestClient
from pydantic import ValidationError
from taste_profile import TasteProfile

import api


def test_run_request_defaults_and_strips_query() -> None:
    assert api.RunRequest().model_dump() == {"query": None, "count": 3, "exploration": 50}
    assert api.RunRequest(query="  daft punk ").query == "daft punk"


@pytest.mark.parametrize(
    "fields",
    [{"query": "   "}, {"query": "x" * 201}, {"count": 0}, {"count": 51}, {"exploration": -1}, {"exploration": 101}],
)
def test_run_request_rejects_invalid_values(fields: dict) -> None:
    with pytest.raises(ValidationError):
        api.RunRequest(**fields)


def test_job_publish_and_finish_update_state() -> None:
    job = api.Job(api.RunRequest())

    job.publish({"type": "a"})
    job.finish()

    assert job.events == [{"type": "a"}]
    assert job.finished


def test_stream_formats_events_with_ids_and_ends_when_finished() -> None:
    job = api.Job(api.RunRequest())
    job.publish({"type": "a"})
    job.publish({"type": "b"})
    job.finish()

    assert list(api._stream(job, 0)) == [
        f"id: 0\ndata: {json.dumps({'type': 'a'})}\n\n",
        f"id: 1\ndata: {json.dumps({'type': 'b'})}\n\n",
    ]


def test_stream_resumes_from_the_given_index() -> None:
    job = api.Job(api.RunRequest())
    job.publish({"type": "a"})
    job.publish({"type": "b"})
    job.finish()

    assert list(api._stream(job, 1)) == [f"id: 1\ndata: {json.dumps({'type': 'b'})}\n\n"]


def test_stream_sends_keepalive_while_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "KEEPALIVE_SECONDS", 0.01)
    job = api.Job(api.RunRequest())
    stream = api._stream(job, 0)

    assert next(stream) == ": keepalive\n\n"

    job.publish({"type": "a"})
    assert next(stream) == f"id: 0\ndata: {json.dumps({'type': 'a'})}\n\n"
    job.finish()
    assert list(stream) == []


def _run_worker(jobs: "queue.Queue[api.Job]", appdb: AppDb) -> None:
    threading.Thread(target=api._process_jobs, args=(jobs, appdb), daemon=True).start()


def _wait_until_finished(job: api.Job) -> None:
    with job.cond:
        assert job.cond.wait_for(lambda: job.finished, timeout=5)


def test_process_jobs_publishes_run_events_then_finishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple] = []

    def fake_run(query, count, exploration, appdb):
        calls.append((query, count, exploration))
        yield {"type": "started"}
        yield {"type": "done"}

    monkeypatch.setattr(api, "run", fake_run)
    jobs: queue.Queue[api.Job] = queue.Queue()
    job = api.Job(api.RunRequest(query="q", count=2, exploration=10))
    jobs.put(job)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(job)

    assert calls == [("q", 2, 10)]
    assert job.events == [{"type": "started"}, {"type": "done"}]


def test_process_jobs_reports_errors_and_keeps_serving(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(query, count, exploration, appdb):
        if query == "bad":
            raise RuntimeError("model failed")
        yield {"type": "done"}

    monkeypatch.setattr(api, "run", fake_run)
    jobs: queue.Queue[api.Job] = queue.Queue()
    bad, good = api.Job(api.RunRequest(query="bad")), api.Job(api.RunRequest(query="good"))
    jobs.put(bad)
    jobs.put(good)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(good)

    assert bad.events == [{"type": "error", "message": "model failed"}]
    assert bad.finished
    assert good.events == [{"type": "done"}]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    # Not used as a context manager, so the real lifespan (and app.db) never starts.
    api.app.state.appdb = AppDb(tmp_path / "app.db")
    api.app.state.jobs = {}
    api.app.state.queue = queue.Queue()
    return TestClient(api.app)


def _save_taste() -> None:
    api.app.state.appdb.save_taste(TasteProfile(liked_genres=["Rock"]))


def _add_song(video_id: str, title: str = "Title", artist: str = "Artist", recommended: bool = True) -> None:
    api.app.state.appdb.add_song(
        video_id, title, artist, "u", 0.9 if recommended else 0.1, recommended, "q", np.zeros(2, dtype=np.float32), "m"
    )


def test_start_run_without_a_taste_is_409(client: TestClient) -> None:
    response = client.post("/api/runs", json={"query": "daft punk"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Set your taste first"}
    assert api.app.state.queue.empty()


def test_start_run_queues_a_job_and_returns_its_id(client: TestClient) -> None:
    _save_taste()

    response = client.post("/api/runs", json={"query": "daft punk", "count": 2})

    assert response.status_code == 202
    run_id = response.json()["id"]
    job = api.app.state.jobs[run_id]
    assert job.request == api.RunRequest(query="daft punk", count=2)
    assert api.app.state.queue.get_nowait() is job


def test_start_run_rejects_invalid_body(client: TestClient) -> None:
    _save_taste()

    assert client.post("/api/runs", json={"count": 0}).status_code == 422


def test_get_run_events_streams_published_events(client: TestClient) -> None:
    job = api.Job(api.RunRequest())
    job.publish({"type": "started"})
    job.publish({"type": "done"})
    job.finish()
    api.app.state.jobs["r1"] = job

    response = client.get("/api/runs/r1/events")

    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == 'id: 0\ndata: {"type": "started"}\n\nid: 1\ndata: {"type": "done"}\n\n'


def test_get_run_events_resumes_after_last_event_id(client: TestClient) -> None:
    job = api.Job(api.RunRequest())
    job.publish({"type": "started"})
    job.publish({"type": "done"})
    job.finish()
    api.app.state.jobs["r1"] = job

    response = client.get("/api/runs/r1/events", headers={"Last-Event-ID": "0"})

    assert response.text == 'id: 1\ndata: {"type": "done"}\n\n'


def test_get_run_events_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/runs/missing/events").status_code == 404


def test_list_songs_is_empty_for_a_new_database(client: TestClient) -> None:
    assert client.get("/api/songs").json() == {"items": [], "total": 0, "page": 1, "page_size": 24}


def test_list_songs_returns_a_page_with_score_recommended_and_rating(client: TestClient) -> None:
    _add_song("a", "Alpha")
    _add_song("b", "Beta", recommended=False)
    client.put("/api/songs/a/feedback", json={"rating": 1})

    body = client.get("/api/songs", params={"page_size": 1}).json()

    assert (body["total"], body["page"], body["page_size"]) == (2, 1, 1)
    [song] = body["items"]
    assert song["video_id"] == "b"
    assert (song["score"], song["recommended"], song["rating"]) == (0.1, False, None)
    assert "description" not in song and "taste_version" not in song
    assert client.get("/api/songs", params={"page_size": 1, "page": 2}).json()["items"][0]["rating"] == 1
    assert client.get("/api/songs", params={"page": 9}).json()["items"] == []
    assert client.get("/api/songs", params={"page": 9}).json()["total"] == 2


def test_list_songs_filters_searches_and_sorts(client: TestClient) -> None:
    _add_song("a", "Alpha", "Radiohead")
    _add_song("b", "Beta", "Other", recommended=False)

    def ids(**params) -> list[str]:
        return [s["video_id"] for s in client.get("/api/songs", params=params).json()["items"]]

    assert ids(recommended="true") == ["a"]
    assert ids(recommended="false") == ["b"]
    assert ids(q="  RADIO ") == ["a"]
    assert ids(sort="oldest") == ["a", "b"]


@pytest.mark.parametrize(
    "params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"q": "   "}, {"q": "x" * 201}, {"sort": "random"}]
)
def test_list_songs_rejects_invalid_parameters(client: TestClient, params: dict) -> None:
    assert client.get("/api/songs", params=params).status_code == 422


def test_put_feedback_creates_updates_and_resets_the_timestamp(client: TestClient) -> None:
    _add_song("a")

    created = client.put("/api/songs/a/feedback", json={"rating": 1})
    updated = client.put("/api/songs/a/feedback", json={"rating": -1})

    assert created.status_code == 200
    assert created.json()["rating"] == 1
    assert updated.json() == {"video_id": "a", "rating": -1, "created_at": updated.json()["created_at"]}


def test_put_feedback_errors(client: TestClient) -> None:
    _add_song("a")

    assert client.put("/api/songs/missing/feedback", json={"rating": 1}).json() == {"detail": "Unknown song"}
    assert client.put("/api/songs/a/feedback", json={"rating": 0}).status_code == 422


def test_delete_feedback_clears_the_rating(client: TestClient) -> None:
    _add_song("a")
    client.put("/api/songs/a/feedback", json={"rating": 1})

    assert client.delete("/api/songs/a/feedback").status_code == 204
    assert client.delete("/api/songs/a/feedback").status_code == 204
    assert client.get("/api/songs").json()["items"][0]["rating"] is None
    assert client.delete("/api/songs/missing/feedback").status_code == 404


def test_static_files_must_be_revalidated(client: TestClient) -> None:
    response = client.get("/app.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_get_taste_is_null_when_empty(client: TestClient) -> None:
    response = client.get("/api/taste")

    assert response.status_code == 200
    assert response.json() is None


def test_put_taste_saves_the_normalized_profile(client: TestClient) -> None:
    response = client.put("/api/taste", json={"profile": {"liked_genres": [" Rock ", "rock"], "liked_artists": ["Flume"]}})

    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == {
        "liked_genres": ["Rock"],
        "liked_artists": ["Flume"],
        "disliked_genres": [],
        "disliked_artists": [],
        "notes": "",
    }
    assert client.get("/api/taste").json() == body


def test_put_taste_rejects_invalid_input_without_saving(client: TestClient) -> None:
    response = client.put("/api/taste", json={"profile": {"liked_genres": []}})

    assert response.status_code == 422
    assert response.json() == {"detail": "Choose at least one liked genre"}
    assert client.get("/api/taste").json() is None


def test_run_is_allowed_after_saving_a_taste(client: TestClient) -> None:
    assert client.post("/api/runs", json={}).status_code == 409
    client.put("/api/taste", json={"profile": {"liked_genres": ["Rock"]}})

    assert client.post("/api/runs", json={}).status_code == 202
