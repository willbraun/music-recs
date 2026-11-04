import json
import queue
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, Iterator

import uvicorn
from appdb import AppDb
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from model_download import (MODEL_IDS, begin_download, get_download,
                            get_model_size, is_download_active,
                            is_model_downloaded, remove_model)
from pipeline import NO_TASTE_MESSAGE, download_missing_models, run
from pydantic import BaseModel, Field, StringConstraints
from taste_profile import Taste, TasteProfile, normalize_taste

# The API only serves /api on 127.0.0.1 with no authentication; the frontend runs separately and proxies /api here.
# Errors are {"detail": ...}: a string for 404, 409 and the taste 422, FastAPI's list of objects for other 422s.
KEEPALIVE_SECONDS = 15
DEFAULT_PAGE_SIZE = 50


class RunRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    count: int = Field(3, ge=1, le=50)
    exploration: int = Field(50, ge=0, le=100)


class TasteRequest(BaseModel):
    profile: TasteProfile


@dataclass
class Job:
    # Events are kept for the life of the process so a reloaded client can replay them; ids are in-memory only.
    # A job is either a run (request) or the download of one model (model_id), whose progress clients read from /api/models.
    request: RunRequest | None = None
    model_id: str | None = None
    events: list[dict] = field(default_factory=list)
    finished: bool = False
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
    assert job.request is not None
    return run(job.request.query, job.request.count, job.request.exploration, appdb)


def _process_jobs(jobs: "queue.Queue[Job]", appdb: AppDb) -> None:
    # A single worker serializes runs and downloads, since there is one model on one device.
    while True:
        job = jobs.get()
        try:
            for event in _generate_events(job, appdb):
                job.publish(event)
        except Exception as e:
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


app = FastAPI(lifespan=manage_lifespan)


@app.post("/api/runs", status_code=202)
def start_run(body: RunRequest, request: Request) -> dict:
    if request.app.state.appdb.get_current_taste() is None:
        raise HTTPException(status_code=409, detail=NO_TASTE_MESSAGE)
    job = Job(body)
    run_id = uuid.uuid4().hex
    request.app.state.jobs[run_id] = job
    request.app.state.queue.put(job)
    return {"id": run_id}


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
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = DEFAULT_PAGE_SIZE,
) -> dict:
    appdb: AppDb = request.app.state.appdb
    # A page past the last returns items: [] with the correct total.
    items = appdb.list_songs(limit=page_size, offset=(page - 1) * page_size)
    return {"items": items, "total": appdb.count_songs(), "page": page, "page_size": page_size}


def _serialize_taste(taste: Taste) -> dict:
    return {"profile": taste.profile.model_dump(), "text": taste.text, "updated_at": taste.updated_at}


@app.get("/api/taste")
def get_taste(request: Request) -> dict | None:
    taste = request.app.state.appdb.get_current_taste()
    return None if taste is None else _serialize_taste(taste)


@app.put("/api/taste")
def save_taste(body: TasteRequest, request: Request) -> dict:
    try:
        profile = normalize_taste(body.profile)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Saving during a run is fine: a run reads the taste once when it starts.
    return _serialize_taste(request.app.state.appdb.save_taste(profile))


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


if __name__ == "__main__":
    # Local only; short graceful shutdown because open event streams would otherwise block Ctrl-C.
    uvicorn.run(app, host="127.0.0.1", port=8000, timeout_graceful_shutdown=3)
