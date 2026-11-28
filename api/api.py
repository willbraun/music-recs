import json
import logging
import multiprocessing
import os
import queue
import sys
import threading
import uuid
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, field
from typing import Annotated, Iterator

import uvicorn
from appdb import AppDb
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from model_download import (MODEL_IDS, begin_download, get_download,
                            get_model_size, is_download_active,
                            is_model_downloaded, remove_model)
from paths import IS_FROZEN, get_frontend_dir, get_log_path, get_port
from pipeline import NO_TASTE_MESSAGE, download_missing_models, run
from pydantic import BaseModel, Field, StringConstraints, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from taste_profile import Taste, TasteProfile, normalize_taste

# Dev: the API only serves /api and the frontend runs separately on Vite, which proxies /api here.
# Packaged (see paths.get_frontend_dir): it also serves the built frontend, so the app has one http://localhost origin.
# No authentication, bound to 127.0.0.1 only; LocalOnlyMiddleware rejects non-loopback Hosts and cross-origin requests.
# Songs, taste and runs act for the profile in the X-Profile-Id header; models are shared by all profiles.
# Errors are {"detail": ...}: a string for 400, 404, 409 and the taste 422, FastAPI's list of objects for other 422s.
KEEPALIVE_SECONDS = 15
DEFAULT_PAGE_SIZE = 50
MAX_LOG_BYTES = 5_000_000

logger = logging.getLogger(__name__)


class RunRequest(BaseModel):
    count: int = Field(4, ge=1, le=50)
    exploration: int = Field(50, ge=0, le=100)


class TasteRequest(BaseModel):
    profile: TasteProfile


MAX_PROFILE_NAME_CHARS = 30
MAX_AVATAR_CHARS = 16


class ProfileRequest(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_PROFILE_NAME_CHARS)]
    avatar: Annotated[str, Field(min_length=1, max_length=MAX_AVATAR_CHARS)]

    @field_validator("avatar")
    @classmethod
    def check_avatar_is_emoji(cls, avatar: str) -> str:
        # A multi-codepoint emoji (flags, ZWJ sequences) is fine; letters, digits and spaces are not.
        if any(char.isalnum() or char.isspace() for char in avatar):
            raise ValueError("Avatar must be an emoji")
        return avatar


@dataclass
class Job:
    # Events are kept for the life of the process so a reloaded client can replay them; ids are in-memory only.
    # A job is either a run (request) or the download of one model (model_id), whose progress clients read from /api/models.
    request: RunRequest | None = None
    profile_id: int | None = None
    model_id: str | None = None
    events: list[dict] = field(default_factory=list)
    finished: bool = False
    # Set by a client; the worker stops at the next event, so a step already in progress completes first.
    cancelled: bool = False
    cond: threading.Condition = field(default_factory=threading.Condition)

    def publish(self, event: dict) -> None:
        with self.cond:
            self.events.append(event)
            self.cond.notify_all()

    def finish(self) -> None:
        with self.cond:
            self.finished = True
            self.cond.notify_all()


def _generate_events(job: Job, appdb: AppDb) -> Iterator[dict]:
    if job.model_id is not None:
        return download_missing_models([job.model_id])
    assert job.request is not None and job.profile_id is not None
    return run(job.profile_id, job.request.count, job.request.exploration, appdb)


def _process_jobs(jobs: "queue.Queue[Job]", appdb: AppDb) -> None:
    # A single worker serializes runs and downloads, since there is one model on one device.
    while True:
        job = jobs.get()
        try:
            is_stopped = job.cancelled
            if not is_stopped:
                with closing(_generate_events(job, appdb)) as events:
                    for event in events:
                        job.publish(event)
                        if job.cancelled and event["type"] != "done":
                            is_stopped = True
                            break
            if is_stopped:
                job.publish({"type": "cancelled"})
        except Exception as e:
            logger.exception("Job failed")
            job.publish({"type": "error", "message": str(e)})
        finally:
            job.finish()


def _stream(job: Job, start: int) -> Iterator[str]:
    # The SSE event id is the event's index in job.events; the stream ends once the job has finished and is drained.
    index = start
    while True:
        with job.cond:
            if index >= len(job.events) and not job.finished:
                job.cond.wait(KEEPALIVE_SECONDS)
            batch = job.events[index:]
            finished = job.finished
        for event in batch:
            yield f"id: {index}\ndata: {json.dumps(event)}\n\n"
            index += 1
        if not batch:
            if finished:
                return
            yield ": keepalive\n\n"


@asynccontextmanager
async def manage_lifespan(app: FastAPI):
    app.state.appdb = AppDb()
    app.state.jobs = {}
    app.state.queue = queue.Queue()
    threading.Thread(target=_process_jobs, args=(app.state.queue, app.state.appdb), daemon=True).start()
    yield


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "[::1]"}


class LocalOnlyMiddleware:
    """Rejects requests a web page could send to this local API: a rebound DNS name (Host) or another origin (Origin)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
            host = headers.get("host", "")
            origin = headers.get("origin")
            # Same-origin only: the packaged app and the Vite proxy both keep the Host the browser used.
            hostname = host.partition("]")[0] + "]" if host.startswith("[") else host.partition(":")[0]
            allowed = hostname in LOOPBACK_HOSTS
            if allowed and origin is not None:
                allowed = origin == f"http://{host}"
            if not allowed:
                if scope["type"] == "http":
                    await JSONResponse({"detail": "Forbidden"}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app = FastAPI(lifespan=manage_lifespan)
app.add_middleware(LocalOnlyMiddleware)


def get_profile_id(request: Request, profile_id: Annotated[int | None, Header(alias="X-Profile-Id")] = None) -> int:
    """The profile a request acts for, sent by the client on every profile-scoped call."""
    if profile_id is None:
        raise HTTPException(status_code=400, detail="Missing X-Profile-Id header")
    if request.app.state.appdb.get_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="Unknown profile")
    return profile_id


ProfileId = Annotated[int, Depends(get_profile_id)]


@app.get("/api/profiles")
def list_profiles(request: Request) -> dict:
    return {"items": request.app.state.appdb.list_profiles()}


@app.post("/api/profiles", status_code=201)
def add_profile(body: ProfileRequest, request: Request) -> dict:
    return request.app.state.appdb.add_profile(body.name, body.avatar)


@app.get("/api/profiles/{profile_id}")
def get_profile(profile_id: int, request: Request) -> dict:
    profile = request.app.state.appdb.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown profile")
    return profile


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, body: ProfileRequest, request: Request) -> dict:
    profile = request.app.state.appdb.update_profile(profile_id, body.name, body.avatar)
    if profile is None:
        raise HTTPException(status_code=404, detail="Unknown profile")
    return profile


@app.delete("/api/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: int, request: Request) -> None:
    if any(job.profile_id == profile_id and not job.finished for job in list(request.app.state.jobs.values())):
        raise HTTPException(status_code=409, detail="Wait for this profile's run to finish")
    if not request.app.state.appdb.delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="Unknown profile")


@app.post("/api/runs", status_code=202)
def start_run(body: RunRequest, request: Request, profile_id: ProfileId) -> dict:
    if request.app.state.appdb.get_current_taste(profile_id) is None:
        raise HTTPException(status_code=409, detail=NO_TASTE_MESSAGE)
    job = Job(body, profile_id)
    run_id = uuid.uuid4().hex
    request.app.state.jobs[run_id] = job
    request.app.state.queue.put(job)
    return {"id": run_id}


@app.delete("/api/runs/{run_id}", status_code=204)
def cancel_run(run_id: str, request: Request, profile_id: ProfileId) -> None:
    job = request.app.state.jobs.get(run_id)
    if job is None or job.request is None or job.profile_id != profile_id:
        raise HTTPException(status_code=404, detail="Unknown run")
    # Idempotent: a finished run has nothing left to cancel.
    job.cancelled = True


@app.get("/api/runs/{run_id}/events")
def get_run_events(run_id: str, request: Request, last_event_id: Annotated[int | None, Header()] = None) -> StreamingResponse:
    job = request.app.state.jobs.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown run")
    # Without Last-Event-ID every event is replayed, so a page reload can reattach to a run.
    start = 0 if last_event_id is None else last_event_id + 1
    return StreamingResponse(_stream(job, start), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/songs")
def list_songs(
    request: Request,
    profile_id: ProfileId,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = DEFAULT_PAGE_SIZE,
) -> dict:
    appdb: AppDb = request.app.state.appdb
    # A page past the last returns items: [] with the correct total.
    items = appdb.list_songs(profile_id, limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "total": appdb.count_songs(profile_id), "page": page, "page_size": page_size}


def _serialize_taste(taste: Taste) -> dict:
    return {"profile": taste.profile.model_dump(), "text": taste.text, "updated_at": taste.updated_at}


@app.get("/api/taste")
def get_taste(request: Request, profile_id: ProfileId) -> dict | None:
    taste = request.app.state.appdb.get_current_taste(profile_id)
    return None if taste is None else _serialize_taste(taste)


@app.put("/api/taste")
def save_taste(body: TasteRequest, request: Request, profile_id: ProfileId) -> dict:
    try:
        profile = normalize_taste(body.profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Saving during a run is fine: a run reads the taste once when it starts.
    return _serialize_taste(request.app.state.appdb.save_taste(profile_id, profile))


_download_start_lock = threading.Lock()


def _require_model(model_id: str) -> None:
    if model_id not in MODEL_IDS:
        raise HTTPException(status_code=404, detail="Unknown model")


def _is_busy(request: Request) -> bool:
    return any(not job.finished for job in list(request.app.state.jobs.values()))


def _serialize_model(model_id: str) -> dict:
    # Files can look complete while a download is still writing them, so an active download is never reported as downloaded.
    downloaded = not is_download_active(model_id) and is_model_downloaded(model_id)
    return {
        "id": model_id,
        "downloaded": downloaded,
        "size_bytes": get_model_size(model_id, downloaded),
        "download": None if downloaded else get_download(model_id),
    }


@app.get("/api/models")
def list_models(request: Request) -> dict:
    # busy: a run or download is queued or running, so models cannot be removed.
    return {"items": [_serialize_model(model_id) for model_id in MODEL_IDS], "busy": _is_busy(request)}


@app.post("/api/models/{model_id:path}/download", status_code=202)
def start_model_download(model_id: str, request: Request) -> dict:
    _require_model(model_id)
    # Idempotent: a download already queued or running (from a run or this page) is reported, not repeated.
    with _download_start_lock:
        if not is_download_active(model_id):
            if is_model_downloaded(model_id):
                raise HTTPException(status_code=409, detail="Model is already downloaded")
            begin_download(model_id, None)
            job = Job(model_id=model_id)
            request.app.state.jobs[uuid.uuid4().hex] = job
            request.app.state.queue.put(job)
    return _serialize_model(model_id)


@app.delete("/api/models/{model_id:path}", status_code=204)
def delete_model(model_id: str, request: Request) -> None:
    _require_model(model_id)
    if _is_busy(request):
        raise HTTPException(status_code=409, detail="Wait for the current run or download to finish")
    if not is_model_downloaded(model_id):
        raise HTTPException(status_code=409, detail="Model is not downloaded")
    remove_model(model_id)


def _redirect_output_to_log() -> None:
    # Launched from Finder the app has no terminal, so stdout/stderr (including ffmpeg's) go to a file in the data dir.
    path = get_log_path()
    if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
        path.unlink()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd, sys.stdout.fileno())
    os.dup2(fd, sys.stderr.fileno())
    os.close(fd)
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)


class SpaStaticFiles(StaticFiles):
    # adapter-static emits only index.html, so client-side routes like /songs fall back to it.
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as e:
            # An unknown /api path must stay a 404, not become the app shell.
            if e.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


frontend_dir = get_frontend_dir()
if frontend_dir is not None:
    # Mounted last so it only receives requests no /api route matched.
    app.mount("/", SpaStaticFiles(directory=frontend_dir, html=True), name="frontend")


if __name__ == "__main__":
    # Required so a frozen build's spawned download processes run their target instead of the server.
    multiprocessing.freeze_support()
    if IS_FROZEN:
        _redirect_output_to_log()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # Local only; short graceful shutdown because open event streams would otherwise block Ctrl-C.
    uvicorn.run(app, host="127.0.0.1", port=get_port(), timeout_graceful_shutdown=3)
