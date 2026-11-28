import json
import queue
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from appdb import AppDb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from model_download import begin_download, fail_download
from pydantic import ValidationError
from taste_profile import TasteProfile

PROFILE_ID = 1

import api


def test_run_request_defaults_and_strips_query() -> None:
    assert api.RunRequest().model_dump() == {"count": 4, "exploration": 50}


@pytest.mark.parametrize(
    "fields",
    [{"count": 0}, {"count": 51}, {"exploration": -1}, {"exploration": 101}],
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

    def fake_run(profile_id, count, exploration, appdb):
        calls.append((profile_id, count, exploration))
        yield {"type": "started"}
        yield {"type": "done"}

    monkeypatch.setattr(api, "run", fake_run)
    jobs: queue.Queue[api.Job] = queue.Queue()
    job = api.Job(api.RunRequest(count=2, exploration=10), PROFILE_ID)
    jobs.put(job)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(job)

    assert calls == [(PROFILE_ID, 2, 10)]
    assert job.events == [{"type": "started"}, {"type": "done"}]


def test_process_jobs_reports_errors_and_keeps_serving(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(profile_id, count, exploration, appdb):
        if count == 1:
            raise RuntimeError("model failed")
        yield {"type": "done"}

    monkeypatch.setattr(api, "run", fake_run)
    jobs: queue.Queue[api.Job] = queue.Queue()
    bad, good = api.Job(api.RunRequest(count=1), PROFILE_ID), api.Job(api.RunRequest(count=2), PROFILE_ID)
    jobs.put(bad)
    jobs.put(good)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(good)

    assert bad.events == [{"type": "error", "message": "model failed"}]
    assert bad.finished
    assert good.events == [{"type": "done"}]


def test_process_jobs_stops_a_cancelled_run_and_keeps_serving(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    job = api.Job(api.RunRequest(), PROFILE_ID)
    closed: list[bool] = []

    def fake_run(profile_id, count, exploration, appdb):
        try:
            yield {"type": "started"}
            job.cancelled = True
            yield {"type": "analyzing"}
            yield {"type": "never"}
        finally:
            closed.append(True)

    monkeypatch.setattr(api, "run", fake_run)
    jobs: queue.Queue[api.Job] = queue.Queue()
    queued = api.Job(api.RunRequest(), PROFILE_ID)
    queued.cancelled = True
    jobs.put(job)
    jobs.put(queued)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(job)
    _wait_until_finished(queued)

    assert job.events == [{"type": "started"}, {"type": "analyzing"}, {"type": "cancelled"}]
    assert closed == [True]
    assert queued.events == [{"type": "cancelled"}]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    # Not used as a context manager, so the real lifespan (and app.db) never starts.
    api.app.state.appdb = AppDb(tmp_path / "app.db")
    api.app.state.appdb.add_profile("Ann", "🎸")
    api.app.state.jobs = {}
    api.app.state.queue = queue.Queue()
    return TestClient(api.app, base_url="http://localhost", headers={"X-Profile-Id": str(PROFILE_ID)})


@pytest.mark.parametrize("host", ["evil.example", "evil.example:8000", "localhost.evil.example"])
def test_rejects_non_loopback_host(client: TestClient, host: str) -> None:
    assert client.get("/api/taste", headers={"Host": host}).status_code == 403


def test_rejects_cross_origin_request(client: TestClient) -> None:
    response = client.post("/api/runs", json={}, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_accepts_same_origin_request(client: TestClient) -> None:
    response = client.get("/api/taste", headers={"Host": "localhost:5173", "Origin": "http://localhost:5173"})
    assert response.status_code != 403


def test_profile_scoped_endpoints_require_a_known_profile(client: TestClient) -> None:
    assert client.get("/api/songs", headers={"X-Profile-Id": "99"}).status_code == 404
    assert client.get("/api/taste", headers={"X-Profile-Id": "99"}).status_code == 404
    client.headers.pop("X-Profile-Id")
    assert client.get("/api/songs").status_code == 400
    assert client.get("/api/models").status_code == 200


def test_songs_and_taste_belong_to_the_requesting_profile(client: TestClient) -> None:
    other = client.post("/api/profiles", json={"name": "Bob", "avatar": "🎹"}).json()["id"]
    api.app.state.appdb.add_song(PROFILE_ID, "abc", "T", "A", "u", True, 0.9, "q")
    client.put("/api/taste", json={"profile": {"liked_genres": ["Rock"]}})

    headers = {"X-Profile-Id": str(other)}
    assert client.get("/api/songs", headers=headers).json()["total"] == 0
    assert client.get("/api/taste", headers=headers).json() is None
    assert client.get("/api/songs").json()["total"] == 1


def test_profiles_can_be_created_edited_listed_and_deleted(client: TestClient) -> None:
    created = client.post("/api/profiles", json={"name": "  Bob  ", "avatar": "🎹"})
    assert created.status_code == 201
    assert created.json()["name"] == "Bob"
    profile_id = created.json()["id"]

    assert client.put(f"/api/profiles/{profile_id}", json={"name": "Bobby", "avatar": "👨‍🎤"}).json()["name"] == "Bobby"
    assert client.get(f"/api/profiles/{profile_id}").json()["avatar"] == "👨‍🎤"
    assert [profile["name"] for profile in client.get("/api/profiles").json()["items"]] == ["Ann", "Bobby"]
    assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
    assert client.get(f"/api/profiles/{profile_id}").status_code == 404
    assert client.delete(f"/api/profiles/{profile_id}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"name": "", "avatar": "🎸"},
        {"name": "   ", "avatar": "🎸"},
        {"name": "x" * 31, "avatar": "🎸"},
        {"name": "Bob", "avatar": ""},
        {"name": "Bob", "avatar": "A"},
        {"name": "Bob", "avatar": "7"},
        {"name": "Bob", "avatar": "🎸 "},
    ],
)
def test_profiles_reject_invalid_input(client: TestClient, body: dict) -> None:
    assert client.post("/api/profiles", json=body).status_code == 422


def test_delete_profile_is_blocked_while_its_run_is_unfinished(client: TestClient) -> None:
    api.app.state.jobs["run"] = api.Job(api.RunRequest(), PROFILE_ID)

    assert client.delete(f"/api/profiles/{PROFILE_ID}").status_code == 409


def test_start_run_queues_a_job_and_returns_its_id(client: TestClient) -> None:
    api.app.state.appdb.save_taste(PROFILE_ID, TasteProfile(liked_genres=["Rock"]))
    response = client.post("/api/runs", json={"count": 2})

    assert response.status_code == 202
    run_id = response.json()["id"]
    job = api.app.state.jobs[run_id]
    assert job.request == api.RunRequest(count=2)
    assert api.app.state.queue.get_nowait() is job


def test_start_run_requires_a_saved_taste(client: TestClient) -> None:
    response = client.post("/api/runs", json={})

    assert (response.status_code, response.json()) == (409, {"detail": "Set your taste first"})
    assert api.app.state.queue.empty()


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


def test_cancel_run_flags_only_the_owners_run(client: TestClient) -> None:
    other = client.post("/api/profiles", json={"name": "Bob", "avatar": "🎹"}).json()["id"]
    job = api.Job(api.RunRequest(), PROFILE_ID)
    api.app.state.jobs["run"] = job

    assert client.delete("/api/runs/run", headers={"X-Profile-Id": str(other)}).status_code == 404
    assert not job.cancelled
    assert client.delete("/api/runs/run").status_code == 204
    assert job.cancelled
    assert client.delete("/api/runs/missing").status_code == 404


def test_get_run_events_unknown_run_is_404(client: TestClient) -> None:
    assert client.get("/api/runs/missing/events").status_code == 404


def test_list_songs_flags_recommended_songs(client: TestClient) -> None:
    appdb: AppDb = api.app.state.appdb
    appdb.add_song(PROFILE_ID, "yes", "Yes", "A", "u", True, 0.9, "q")
    appdb.add_song(PROFILE_ID, "no", "No", "A", "u", False, 0.6, "q")

    songs = {song["video_id"]: song for song in client.get("/api/songs").json()["items"]}

    assert {video_id: song["recommended"] for video_id, song in songs.items()} == {"yes": True, "no": False}
    assert songs["yes"]["confidence"] == 0.9
    assert "description" not in songs["yes"]
    assert songs["yes"]["title"] == "Yes"


def test_list_songs_is_empty_for_a_new_database(client: TestClient) -> None:
    assert client.get("/api/songs").json() == {"items": [], "total": 0, "page": 1, "page_size": 50}


def test_list_songs_paginates_by_fifty_newest_first(client: TestClient) -> None:
    appdb: AppDb = api.app.state.appdb
    for i in range(120):
        appdb.add_song(PROFILE_ID, f"v{i}", "T", "A", "u", True, 0.9, "q")

    first = client.get("/api/songs").json()
    last = client.get("/api/songs", params={"page": 3}).json()
    beyond = client.get("/api/songs", params={"page": 4}).json()

    assert (first["total"], len(first["items"]), first["items"][0]["video_id"]) == (120, 50, "v119")
    assert (last["page"], [song["video_id"] for song in last["items"]][:1], len(last["items"])) == (3, ["v19"], 20)
    assert beyond["items"] == []


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}])
def test_list_songs_rejects_invalid_parameters(client: TestClient, params: dict) -> None:
    assert client.get("/api/songs", params=params).status_code == 422


def test_get_taste_is_null_when_none_is_saved(client: TestClient) -> None:
    response = client.get("/api/taste")

    assert (response.status_code, response.json()) == (200, None)


def test_put_taste_saves_normalizes_and_renders_the_text(client: TestClient) -> None:
    body = {"profile": {"liked_genres": [" Rock ", "rock"], "liked_artists": ["Flume"], "notes": "a\nb"}}

    saved = client.put("/api/taste", json=body)

    assert saved.status_code == 200
    assert saved.json()["profile"] == {
        "liked_genres": ["Rock"],
        "liked_artists": ["Flume"],
        "disliked_genres": [],
        "disliked_artists": [],
        "notes": "a b",
    }
    assert saved.json()["text"] == "I like these genres: Rock. My favorite artists are Flume. Notes: a b"
    assert client.get("/api/taste").json() == saved.json()


def test_put_taste_rejects_invalid_input_and_saves_nothing(client: TestClient) -> None:
    response = client.put("/api/taste", json={"profile": {"notes": "only notes"}})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert client.get("/api/taste").json() is None


def test_start_run_is_accepted_after_saving_a_taste(client: TestClient) -> None:
    client.put("/api/taste", json={"profile": {"liked_genres": ["Rock"]}})

    assert client.post("/api/runs", json={}).status_code == 202


def test_process_jobs_runs_a_download_job_for_its_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_download(model_ids: list[str]):
        calls.append(model_ids)
        yield {"type": "model_downloaded", "model": model_ids[0]}

    monkeypatch.setattr(api, "download_missing_models", fake_download)
    jobs: queue.Queue[api.Job] = queue.Queue()
    job = api.Job(model_id="org/model")
    jobs.put(job)

    _run_worker(jobs, AppDb(tmp_path / "app.db"))
    _wait_until_finished(job)

    assert calls == [["org/model"]]
    assert job.events == [{"type": "model_downloaded", "model": "org/model"}]


@pytest.fixture
def models(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Replaces the Hugging Face cache layer; `downloaded` holds the ids on disk and `removed` the ids deleted."""
    state = SimpleNamespace(downloaded=set(), removed=[])
    monkeypatch.setattr(api, "MODEL_IDS", ("org/a", "org/b"))
    monkeypatch.setattr(api, "is_model_downloaded", lambda model_id: model_id in state.downloaded)
    monkeypatch.setattr(api, "get_model_size", lambda model_id, downloaded: 100 if downloaded else 200)
    monkeypatch.setattr(api, "remove_model", state.removed.append)
    return state


def test_list_models_reports_downloaded_state_size_and_progress(client: TestClient, models: SimpleNamespace) -> None:
    models.downloaded.add("org/a")
    begin_download("org/b", 200)

    body = client.get("/api/models").json()

    assert body["busy"] is False
    assert body["items"][0] == {"id": "org/a", "downloaded": True, "size_bytes": 100, "download": None}
    assert body["items"][1]["downloaded"] is False
    assert body["items"][1]["size_bytes"] == 200
    assert body["items"][1]["download"]["state"] == "pending"


def test_list_models_does_not_report_a_model_as_downloaded_while_it_downloads(client: TestClient, models: SimpleNamespace) -> None:
    models.downloaded.add("org/a")
    begin_download("org/a", 200)

    item = client.get("/api/models").json()["items"][0]

    assert (item["downloaded"], item["download"]["state"]) == (False, "pending")


def test_list_models_hides_a_stale_failure_once_the_model_is_downloaded(client: TestClient, models: SimpleNamespace) -> None:
    fail_download("org/a", "network down")
    models.downloaded.add("org/a")

    assert client.get("/api/models").json()["items"][0]["download"] is None


def test_list_models_is_busy_while_a_job_is_unfinished(client: TestClient, models: SimpleNamespace) -> None:
    job = api.Job(api.RunRequest())
    api.app.state.jobs["r1"] = job
    assert client.get("/api/models").json()["busy"] is True

    job.finish()
    assert client.get("/api/models").json()["busy"] is False


def test_start_model_download_queues_a_job_and_reports_it_pending(client: TestClient, models: SimpleNamespace) -> None:
    response = client.post("/api/models/org/a/download")

    assert response.status_code == 202
    assert response.json()["download"]["state"] == "pending"
    job = api.app.state.queue.get_nowait()
    assert job.model_id == "org/a" and job.request is None
    assert list(api.app.state.jobs.values()) == [job]


def test_start_model_download_is_idempotent_while_active(client: TestClient, models: SimpleNamespace) -> None:
    client.post("/api/models/org/a/download")
    response = client.post("/api/models/org/a/download")

    assert response.status_code == 202
    assert api.app.state.queue.qsize() == 1


def test_start_model_download_retries_after_a_failure(client: TestClient, models: SimpleNamespace) -> None:
    fail_download("org/a", "network down")

    response = client.post("/api/models/org/a/download")

    assert response.json()["download"]["state"] == "pending"
    assert api.app.state.queue.qsize() == 1


def test_start_model_download_rejects_a_downloaded_model(client: TestClient, models: SimpleNamespace) -> None:
    models.downloaded.add("org/a")

    response = client.post("/api/models/org/a/download")

    assert (response.status_code, response.json()) == (409, {"detail": "Model is already downloaded"})
    assert api.app.state.queue.empty()


def test_start_model_download_rejects_an_unknown_model(client: TestClient, models: SimpleNamespace) -> None:
    assert client.post("/api/models/org/nope/download").status_code == 404


def test_delete_model_removes_the_cached_files(client: TestClient, models: SimpleNamespace) -> None:
    models.downloaded.add("org/a")

    response = client.delete("/api/models/org/a")

    assert (response.status_code, models.removed) == (204, ["org/a"])


def test_delete_model_is_blocked_while_a_job_is_unfinished(client: TestClient, models: SimpleNamespace) -> None:
    models.downloaded.add("org/a")
    api.app.state.jobs["r1"] = api.Job(api.RunRequest())

    response = client.delete("/api/models/org/a")

    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    assert models.removed == []


def test_delete_model_rejects_a_model_that_is_not_downloaded(client: TestClient, models: SimpleNamespace) -> None:
    response = client.delete("/api/models/org/a")

    assert (response.status_code, response.json()) == (409, {"detail": "Model is not downloaded"})


def test_delete_model_rejects_an_unknown_model(client: TestClient, models: SimpleNamespace) -> None:
    assert client.delete("/api/models/org/nope").status_code == 404


@pytest.fixture
def spa_client(tmp_path: Path) -> TestClient:
    (tmp_path / "index.html").write_text("<html>shell</html>")
    (tmp_path / "robots.txt").write_text("User-agent: *")
    spa = FastAPI()
    spa.mount("/", api.SpaStaticFiles(directory=tmp_path, html=True))
    return TestClient(spa)


def test_spa_serves_files_and_falls_back_to_the_shell_for_client_routes(spa_client: TestClient) -> None:
    assert spa_client.get("/robots.txt").text == "User-agent: *"
    assert spa_client.get("/songs").text == "<html>shell</html>"


def test_spa_keeps_unknown_api_paths_as_404(spa_client: TestClient) -> None:
    assert spa_client.get("/api/nope").status_code == 404
