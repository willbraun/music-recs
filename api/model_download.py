import multiprocessing
import threading
import time
from collections import deque
from multiprocessing.connection import Connection
from typing import Iterator

# Plain constants so listing models does not import torch or mlx; analyze.py and queries.py load these ids.
QUERY_MODEL_ID = "Qwen/Qwen3-8B-MLX-4bit"
ANALYSIS_MODEL_ID = "FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit"
MODEL_IDS = (QUERY_MODEL_ID, ANALYSIS_MODEL_ID)

POLL_SECONDS = 1.0
SPEED_WINDOW_SECONDS = 5.0
# A failed remote size lookup is retried after this long, so an offline server is not queried on every poll.
SIZE_RETRY_SECONDS = 60.0
# huggingface_hub 2.2.0 internals. The reconstruct bar's total matches the file sizes but it advances in steps as Xet flushes to disk.
# The transfer bar advances continuously, so progress is the larger of the two. The "Fetching N files" bar is skipped.
RECONSTRUCT_BAR_NAME = "huggingface_hub.snapshot_download"
TRANSFER_BAR_NAME = RECONSTRUCT_BAR_NAME + ".transfer"
BYTES_BAR_UNIT = "B"

# A hung connection cannot be cancelled inside a thread, so each attempt runs in a child process that can be killed.
# Spawn because the API is multithreaded; tests swap in fork so the child inherits their patches.
_mp_context = multiprocessing.get_context("spawn")
# A stalled attempt is killed and restarted silently, resuming from the partial files, up to this many times.
STALL_SECONDS = 60.0
MAX_STALL_RETRIES = 5
KILL_GRACE_SECONDS = 5.0


class _ByteCounter:
    """Byte counts in shared memory so the child process can report to the parent."""

    def __init__(self) -> None:
        self._bytes = {name: _mp_context.Value("q", 0) for name in (RECONSTRUCT_BAR_NAME, TRANSFER_BAR_NAME)}

    def add(self, bar_name: str, n: float) -> None:
        counter = self._bytes[bar_name]
        with counter.get_lock():
            counter.value += int(n)

    @property
    def value(self) -> int:
        return max(counter.value for counter in self._bytes.values())


class _SpeedWindow:
    """Average bytes per second over the last SPEED_WINDOW_SECONDS."""

    def __init__(self, start_time: float) -> None:
        self._samples: deque[tuple[float, int]] = deque([(start_time, 0)])

    def update(self, now: float, downloaded: int) -> float:
        self._samples.append((now, downloaded))
        # Keep the newest sample that is at least a window old as the baseline.
        while len(self._samples) > 2 and now - self._samples[1][0] >= SPEED_WINDOW_SECONDS:
            self._samples.popleft()
        oldest_time, oldest_bytes = self._samples[0]
        elapsed = now - oldest_time
        return (downloaded - oldest_bytes) / elapsed if elapsed > 0 else 0.0


def _make_tqdm_class(counter: _ByteCounter):
    # Deferred so importing the pipeline does not load huggingface_hub.
    from huggingface_hub.utils import tqdm

    class CountingTqdm(tqdm):
        def __init__(self, *args, **kwargs):
            # A disabled tqdm skips setting attributes, so the bar is identified from the arguments.
            name = kwargs.get("name")
            is_counted = name in (RECONSTRUCT_BAR_NAME, TRANSFER_BAR_NAME) and kwargs.get("unit") == BYTES_BAR_UNIT
            self._counted_as = name if is_counted else None
            initial = kwargs.get("initial") or 0
            super().__init__(*args, **kwargs)
            if self._counted_as and initial:
                counter.add(self._counted_as, initial)

        # Overridden because a disabled tqdm does not increment `n`.
        def update(self, n=1):
            if self._counted_as and n:
                counter.add(self._counted_as, n)
            return super().update(n)

    return CountingTqdm


def get_download_size(model_id: str) -> int | None:
    """Return the bytes still to download for the model, or None when no file size is known."""
    from huggingface_hub import snapshot_download

    files = snapshot_download(model_id, dry_run=True)
    total = sum(file.file_size or 0 for file in files if file.will_download)
    return total or None


def is_model_downloaded(model_id: str) -> bool:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        snapshot_download(model_id, local_files_only=True)
    except LocalEntryNotFoundError:
        return False
    return True


_remote_sizes: dict[str, tuple[int | None, float]] = {}


def _get_remote_size(model_id: str) -> int | None:
    from huggingface_hub import snapshot_download

    cached = _remote_sizes.get(model_id)
    if cached is not None and (cached[0] is not None or time.monotonic() - cached[1] < SIZE_RETRY_SECONDS):
        return cached[0]
    try:
        files = snapshot_download(model_id, dry_run=True)
        size = sum(file.file_size or 0 for file in files) or None
    except Exception:
        size = None
    _remote_sizes[model_id] = (size, time.monotonic())
    return size


def get_model_size(model_id: str, is_downloaded: bool) -> int | None:
    """Return the model's full size in bytes: from the local cache once downloaded, else from the Hub (None if unreachable)."""
    if is_downloaded:
        from huggingface_hub import scan_cache_dir

        for repo in scan_cache_dir().repos:
            if repo.repo_type == "model" and repo.repo_id == model_id:
                return repo.size_on_disk
    return _get_remote_size(model_id)


def remove_model(model_id: str) -> None:
    """Delete every cached revision of the model."""
    from huggingface_hub import scan_cache_dir

    cache = scan_cache_dir()
    for repo in cache.repos:
        if repo.repo_type == "model" and repo.repo_id == model_id:
            cache.delete_revisions(*(revision.commit_hash for revision in repo.revisions)).execute()


# Download progress per model, shared by runs and the Models page so every client sees the same state.
# "pending" and "downloading" entries are cleared when the download ends; "failed" stays until the next attempt.
_downloads: dict[str, dict] = {}
_downloads_lock = threading.Lock()


def _make_download_state(state: str, total_bytes: int | None) -> dict:
    return {
        "state": state,
        "downloaded_bytes": 0,
        "total_bytes": total_bytes,
        "bytes_per_second": 0.0,
        "seconds_remaining": None,
        "error": None,
    }


def begin_download(model_id: str, total_bytes: int | None) -> None:
    with _downloads_lock:
        _downloads[model_id] = _make_download_state("pending", total_bytes)


def update_download(model_id: str, **fields) -> None:
    with _downloads_lock:
        entry = _downloads.setdefault(model_id, _make_download_state("downloading", None))
        entry.update(state="downloading", **fields)


def fail_download(model_id: str, message: str) -> None:
    with _downloads_lock:
        entry = _downloads.setdefault(model_id, _make_download_state("failed", None))
        entry.update(state="failed", bytes_per_second=0.0, seconds_remaining=None, error=message)


def finish_download(model_id: str) -> None:
    with _downloads_lock:
        if _downloads.get(model_id, {}).get("state") != "failed":
            _downloads.pop(model_id, None)


def get_download(model_id: str) -> dict | None:
    with _downloads_lock:
        entry = _downloads.get(model_id)
        return None if entry is None else dict(entry)


def is_download_active(model_id: str) -> bool:
    entry = get_download(model_id)
    return entry is not None and entry["state"] != "failed"


def _download_in_child(model_id: str, counter: _ByteCounter, error_conn: Connection) -> None:
    from huggingface_hub import snapshot_download

    try:
        snapshot_download(model_id, tqdm_class=_make_tqdm_class(counter))
    except BaseException as e:
        try:
            error_conn.send(e)
        except Exception:
            # Some exceptions cannot be pickled.
            error_conn.send(RuntimeError(str(e)))


def _receive_error(receiver: Connection) -> BaseException | None:
    try:
        return receiver.recv()
    except EOFError:
        return None


def _stop_process(process) -> None:
    if process.is_alive():
        process.terminate()
        process.join(KILL_GRACE_SECONDS)
        if process.is_alive():
            process.kill()
            process.join()


def download_model(model_id: str, total_bytes: int | None) -> Iterator[dict]:
    """Download the model, yielding a download_progress event every POLL_SECONDS and a final one at 100%.

    An attempt with no byte progress for STALL_SECONDS is restarted without any event, up to MAX_STALL_RETRIES times.
    Re-raises any download error so the caller can report it.
    """

    def make_event(downloaded: int, bytes_per_second: float, seconds_remaining: float | None) -> dict:
        return {
            "type": "download_progress",
            "model": model_id,
            "downloaded_bytes": downloaded,
            "total_bytes": total_bytes,
            "bytes_per_second": bytes_per_second,
            "seconds_remaining": seconds_remaining,
        }

    window = _SpeedWindow(time.monotonic())
    # Progress never moves backwards when a retry's counters restart from zero.
    furthest = 0
    stalls = 0
    while True:
        counter = _ByteCounter()
        receiver, sender = _mp_context.Pipe(duplex=False)
        process = _mp_context.Process(target=_download_in_child, args=(model_id, counter, sender), daemon=True)
        process.start()
        sender.close()
        last_value, last_change = 0, time.monotonic()
        is_stalled = False
        try:
            while True:
                process.join(POLL_SECONDS)
                if not process.is_alive():
                    break
                now = time.monotonic()
                current = counter.value
                if current != last_value:
                    last_value, last_change = current, now
                elif now - last_change >= STALL_SECONDS:
                    is_stalled = True
                    break
                downloaded = max(furthest, current)
                if total_bytes is not None:
                    downloaded = min(downloaded, total_bytes)
                speed = window.update(now, downloaded)
                remaining = (total_bytes - downloaded) / speed if total_bytes is not None and speed > 0 else None
                yield make_event(downloaded, speed, remaining)
            if not is_stalled:
                # The pipe reads as EOF, not empty, when the child exited without sending an error.
                if receiver.poll() and (error := _receive_error(receiver)) is not None:
                    raise error
                if process.exitcode != 0:
                    raise RuntimeError(f"The download process exited with code {process.exitcode}")
        finally:
            furthest = max(furthest, counter.value)
            receiver.close()
            _stop_process(process)
        if not is_stalled:
            break
        stalls += 1
        if stalls > MAX_STALL_RETRIES:
            raise TimeoutError(f"The download made no progress for {STALL_SECONDS:.0f} seconds and was stopped")

    yield make_event(total_bytes if total_bytes is not None else furthest, 0.0, 0.0)
