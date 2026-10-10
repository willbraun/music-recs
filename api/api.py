import json
import queue
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Iterator

import uvicorn
from appdb import AppDb
from cache import Cache
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pipeline import run
from pydantic import BaseModel, Field, StringConstraints
from recommend import get_verdict

WEB_DIR = Path(__file__).parent.parent / "web"
KEEPALIVE_SECONDS = 15


class RunRequest(BaseModel):
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    count: int = Field(3, ge=1, le=50)
    exploration: int = Field(50, ge=0, le=100)


@dataclass
class Job:
    request: RunRequest
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


def _process_jobs(jobs: "queue.Queue[Job]", cache: Cache, appdb: AppDb) -> None:
    # A single worker serializes runs, since there is one model on one device.
    while True:
        job = jobs.get()
        try:
            for event in run(job.request.query, job.request.count, job.request.exploration, cache, appdb):
                job.publish(event)
        except Exception as e:
            job.publish({"type": "error", "message": str(e)})
        finally:
            job.finish()


def _stream(job: Job, start: int) -> Iterator[str]:
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
    app.state.cache = Cache()
    app.state.jobs = {}
    app.state.queue = queue.Queue()
    threading.Thread(target=_process_jobs, args=(app.state.queue, app.state.cache, AppDb()), daemon=True).start()
    yield


app = FastAPI(lifespan=manage_lifespan)


@app.post("/api/runs", status_code=202)
def start_run(body: RunRequest, request: Request) -> dict:
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
    start = 0 if last_event_id is None else last_event_id + 1
    return StreamingResponse(_stream(job, start), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/songs")
def list_songs(request: Request) -> list[dict]:
    songs = request.app.state.cache.list_songs()
    return [{**song, "recommended": get_verdict(song["description"]) is True} for song in songs]


# Mounted last so it never shadows the /api routes.
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")


if __name__ == "__main__":
    # Local only; short graceful shutdown because open event streams would otherwise block Ctrl-C.
    uvicorn.run(app, host="127.0.0.1", port=8000, timeout_graceful_shutdown=3)
