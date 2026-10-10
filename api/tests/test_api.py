import json
import queue
import threading
from pathlib import Path

import pytest
from appdb import AppDb
from fastapi.testclient import TestClient
from pydantic import ValidationError

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


def test_start_run_queues_a_job_and_returns_its_id(client: TestClient) -> None:
    response = client.post("/api/runs", json={"query": "daft punk", "count": 2})

    assert response.status_code == 202
    run_id = response.json()["id"]
    job = api.app.state.jobs[run_id]
    assert job.request == api.RunRequest(query="daft punk", count=2)
    assert api.app.state.queue.get_nowait() is job


def test_start_run_rejects_invalid_body(client: TestClient) -> None:
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


def test_list_songs_flags_recommended_songs(client: TestClient) -> None:
    appdb: AppDb = api.app.state.appdb
    appdb.add_song("yes", "Yes", "A", "u", "Verdict: YES (90% confidence)", "q", 1)
    appdb.add_song("no", "No", "A", "u", "Verdict: NO (60% confidence)", "q", 1)
    appdb.add_song("none", "None", "A", "u", "garbled", "q", 1)

    songs = {s["video_id"]: s for s in client.get("/api/songs").json()}

    assert {k: v["recommended"] for k, v in songs.items()} == {"yes": True, "no": False, "none": False}
    assert songs["yes"]["title"] == "Yes"


def test_list_songs_is_empty_for_a_new_database(client: TestClient) -> None:
    assert client.get("/api/songs").json() == []
