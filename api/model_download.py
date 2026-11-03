import threading
import time
from collections import deque
from typing import Iterator

POLL_SECONDS = 1.0
SPEED_WINDOW_SECONDS = 5.0
# huggingface_hub 2.2.0 internals. The reconstruct bar's total matches the file sizes but it advances in steps as Xet flushes to disk.
# The transfer bar advances continuously, so progress is the larger of the two. The "Fetching N files" bar is skipped.
RECONSTRUCT_BAR_NAME = "huggingface_hub.snapshot_download"
TRANSFER_BAR_NAME = RECONSTRUCT_BAR_NAME + ".transfer"
BYTES_BAR_UNIT = "B"


class _ByteCounter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bytes = {RECONSTRUCT_BAR_NAME: 0, TRANSFER_BAR_NAME: 0}

    def add(self, bar_name: str, n: float) -> None:
        with self._lock:
            self._bytes[bar_name] += int(n)

    @property
    def value(self) -> int:
        with self._lock:
            return max(self._bytes.values())


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


def download_model(model_id: str, total_bytes: int | None) -> Iterator[dict]:
    """Download the model, yielding a download_progress event every POLL_SECONDS and a final one at 100%.

    Re-raises any download error so the caller can report it.
    """
    from huggingface_hub import snapshot_download

    counter = _ByteCounter()
    finished = threading.Event()
    errors: list[BaseException] = []

    def work() -> None:
        try:
            snapshot_download(model_id, tqdm_class=_make_tqdm_class(counter))
        except BaseException as e:
            errors.append(e)
        finally:
            finished.set()

    def make_event(downloaded: int, bytes_per_second: float, seconds_remaining: float | None) -> dict:
        return {
            "type": "download_progress",
            "model": model_id,
            "downloaded_bytes": downloaded,
            "total_bytes": total_bytes,
            "bytes_per_second": bytes_per_second,
            "seconds_remaining": seconds_remaining,
        }

    threading.Thread(target=work, daemon=True).start()
    window = _SpeedWindow(time.monotonic())
    while not finished.wait(POLL_SECONDS):
        downloaded = counter.value
        if total_bytes is not None:
            downloaded = min(downloaded, total_bytes)
        speed = window.update(time.monotonic(), downloaded)
        remaining = (total_bytes - downloaded) / speed if total_bytes is not None and speed > 0 else None
        yield make_event(downloaded, speed, remaining)

    if errors:
        raise errors[0]
    yield make_event(total_bytes if total_bytes is not None else counter.value, 0.0, 0.0)
