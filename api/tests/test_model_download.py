import multiprocessing
import time
from types import SimpleNamespace

import model_download
import pytest
from huggingface_hub.errors import LocalEntryNotFoundError
from model_download import (RECONSTRUCT_BAR_NAME, TRANSFER_BAR_NAME,
                            _SpeedWindow, begin_download, download_model,
                            fail_download, finish_download, get_download,
                            get_download_size, get_model_size,
                            is_download_active, is_model_downloaded,
                            remove_model, update_download)


def _files(*sizes: tuple[int | None, bool]) -> list[SimpleNamespace]:
    return [SimpleNamespace(file_size=size, will_download=will_download) for size, will_download in sizes]


def _next_with_bytes(events, downloaded: int) -> dict:
    event = next(events)
    while event["downloaded_bytes"] != downloaded:
        event = next(events)
    return event


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_download, "POLL_SECONDS", 0.01)
    # The child inherits the monkeypatched huggingface_hub, which a spawned process would not.
    monkeypatch.setattr(model_download, "_mp_context", multiprocessing.get_context("fork"))


def _make_event():
    return model_download._mp_context.Event()


def test_get_download_size_sums_only_files_that_will_download(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []

    def fake_snapshot_download(*args, **kwargs):
        calls.append((args, kwargs))
        return _files((100, True), (50, False), (None, True), (25, True))

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    assert get_download_size("org/model") == 125
    assert calls == [(("org/model",), {"dry_run": True})]


def test_get_download_size_is_none_when_no_size_is_known(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: _files((None, True), (50, False)))

    assert get_download_size("org/model") is None


def test_download_model_counts_the_reconstruct_bar_and_ignores_other_bars(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _make_event()

    def fake_snapshot_download(model_id: str, tqdm_class=None):
        # The three bars huggingface_hub creates; the file-count bar must not add bytes.
        reconstruct = tqdm_class(disable=True, name=RECONSTRUCT_BAR_NAME, total=0, initial=10, unit="B")
        transfer = tqdm_class(disable=True, name=TRANSFER_BAR_NAME, total=0, unit="B")
        files = tqdm_class(disable=True, name="huggingface_hub.hf_thread_map", total=3)
        reconstruct.update(90)
        transfer.update(50)
        files.update(1000)
        release.wait(5)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    events = download_model("org/model", 1000)
    event = _next_with_bytes(events, 100)
    release.set()

    assert event["type"] == "download_progress"
    assert event["model"] == "org/model"
    assert event["total_bytes"] == 1000
    final = list(events)[-1]
    assert final["downloaded_bytes"] == 1000
    assert final["seconds_remaining"] == 0.0


def test_download_model_follows_the_transfer_bar_while_reconstruction_lags(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _make_event()

    def fake_snapshot_download(model_id: str, tqdm_class=None):
        tqdm_class(disable=True, name=RECONSTRUCT_BAR_NAME, total=0, unit="B").update(100)
        transfer = tqdm_class(disable=True, name=TRANSFER_BAR_NAME, total=0, unit="B")
        transfer.update(300)
        transfer.update(150)
        release.wait(5)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    events = download_model("org/model", 1000)
    _next_with_bytes(events, 450)
    release.set()
    list(events)


def test_download_model_reports_progress_before_the_final_event(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _make_event()
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: release.wait(5))

    events = download_model("org/model", 1000)
    first = next(events)
    release.set()
    rest = list(events)

    assert first["downloaded_bytes"] == 0
    assert first["bytes_per_second"] == 0
    assert first["seconds_remaining"] is None
    assert rest[-1]["downloaded_bytes"] == 1000


def test_download_model_computes_eta_from_speed(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _make_event()

    def fake_snapshot_download(model_id: str, tqdm_class=None):
        tqdm_class(disable=True, name=RECONSTRUCT_BAR_NAME, total=0, unit="B").update(100)
        release.wait(5)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    events = download_model("org/model", 1000)
    event = next(events)
    while event["downloaded_bytes"] == 0:
        event = next(events)
    release.set()

    assert event["bytes_per_second"] > 0
    assert event["seconds_remaining"] == pytest.approx(900 / event["bytes_per_second"])


def test_download_model_without_a_total_reports_the_counted_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_snapshot_download(model_id: str, tqdm_class=None):
        tqdm_class(disable=True, name=RECONSTRUCT_BAR_NAME, total=0, unit="B").update(40)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    final = list(download_model("org/model", None))[-1]

    assert (final["downloaded_bytes"], final["total_bytes"]) == (40, None)


def test_download_model_reraises_download_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_snapshot_download(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    with pytest.raises(RuntimeError, match="network down"):
        list(download_model("org/model", 1000))


def test_download_model_restarts_a_stalled_attempt_without_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_download, "STALL_SECONDS", 0.3)
    attempts = model_download._mp_context.Value("i", 0)

    def fake_snapshot_download(model_id: str, tqdm_class=None):
        with attempts.get_lock():
            attempts.value += 1
            attempt = attempts.value
        bar = tqdm_class(disable=True, name=TRANSFER_BAR_NAME, total=0, unit="B")
        bar.update(100 if attempt == 1 else 40)
        if attempt == 1:
            time.sleep(60)
        bar.update(60)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    events = list(download_model("org/model", 1000))

    assert attempts.value == 2
    assert [e["downloaded_bytes"] for e in events] == sorted(e["downloaded_bytes"] for e in events)
    assert events[-1]["downloaded_bytes"] == 1000


def test_download_model_gives_up_after_repeated_stalls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(model_download, "STALL_SECONDS", 0.2)
    monkeypatch.setattr(model_download, "MAX_STALL_RETRIES", 1)
    attempts = model_download._mp_context.Value("i", 0)

    def fake_snapshot_download(model_id: str, tqdm_class=None):
        with attempts.get_lock():
            attempts.value += 1
        time.sleep(60)

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    with pytest.raises(TimeoutError, match="no progress"):
        list(download_model("org/model", 1000))

    assert attempts.value == 2


def test_download_model_reports_a_download_process_that_dies(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: os._exit(3))

    with pytest.raises(RuntimeError, match="exited with code 3"):
        list(download_model("org/model", 1000))


def test_download_model_stops_the_child_when_the_consumer_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda *args, **kwargs: time.sleep(60))
    started = []
    real_process = model_download._mp_context.Process

    def record_process(*args, **kwargs):
        started.append(real_process(*args, **kwargs))
        return started[-1]

    monkeypatch.setattr(model_download._mp_context, "Process", record_process, raising=False)
    events = download_model("org/model", 1000)
    next(events)
    events.close()

    assert not started[0].is_alive()


def test_speed_window_averages_over_the_recent_window() -> None:
    window = _SpeedWindow(0.0)

    assert window.update(1.0, 100) == 100
    assert window.update(2.0, 300) == 150
    # Samples older than the window drop out: from t=2 (300 bytes) to t=8 (900 bytes).
    assert window.update(8.0, 900) == pytest.approx(100)


def test_speed_window_is_zero_without_progress() -> None:
    window = _SpeedWindow(0.0)

    assert window.update(1.0, 0) == 0


def test_is_model_downloaded_checks_only_the_local_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple] = []

    def fake_snapshot_download(*args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "org/missing":
            raise LocalEntryNotFoundError("missing")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    assert is_model_downloaded("org/model")
    assert not is_model_downloaded("org/missing")
    assert calls[0] == (("org/model",), {"local_files_only": True})


def _cache(*repos: SimpleNamespace) -> SimpleNamespace:
    deleted: list[tuple[str, ...]] = []

    def delete_revisions(*hashes: str) -> SimpleNamespace:
        return SimpleNamespace(execute=lambda: deleted.append(hashes))

    return SimpleNamespace(repos=list(repos), delete_revisions=delete_revisions, deleted=deleted)


def _repo(repo_id: str, size: int, *hashes: str, repo_type: str = "model") -> SimpleNamespace:
    return SimpleNamespace(
        repo_id=repo_id, repo_type=repo_type, size_on_disk=size, revisions=[SimpleNamespace(commit_hash=h) for h in hashes]
    )


def test_get_model_size_uses_the_local_cache_once_downloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = _cache(_repo("org/other", 1), _repo("org/model", 500, "abc"))
    monkeypatch.setattr("huggingface_hub.scan_cache_dir", lambda: cache)

    assert get_model_size("org/model", True) == 500


def test_get_model_size_sums_every_remote_file_and_caches_it(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_snapshot_download(model_id: str, **kwargs):
        calls.append(model_id)
        return _files((100, True), (50, False), (None, True))

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)

    assert get_model_size("org/model", False) == 150
    assert get_model_size("org/model", False) == 150
    assert calls == ["org/model"]


def test_get_model_size_is_none_when_the_hub_is_unreachable_and_retried_later(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_snapshot_download(model_id: str, **kwargs):
        calls.append(model_id)
        raise OSError("offline")

    monkeypatch.setattr("huggingface_hub.snapshot_download", fake_snapshot_download)
    now = [0.0]
    monkeypatch.setattr(model_download.time, "monotonic", lambda: now[0])

    assert get_model_size("org/model", False) is None
    assert get_model_size("org/model", False) is None
    assert len(calls) == 1
    now[0] = model_download.SIZE_RETRY_SECONDS + 1
    assert get_model_size("org/model", False) is None
    assert len(calls) == 2


def test_remove_model_deletes_every_revision_of_only_that_model(monkeypatch: pytest.MonkeyPatch) -> None:
    cache = _cache(_repo("org/other", 1, "x"), _repo("org/model", 5, "a", "b"), _repo("org/model", 5, "d", repo_type="dataset"))
    monkeypatch.setattr("huggingface_hub.scan_cache_dir", lambda: cache)

    remove_model("org/model")

    assert cache.deleted == [("a", "b")]


def test_download_registry_tracks_progress_and_clears_on_finish() -> None:
    begin_download("org/model", 100)
    assert get_download("org/model") == {
        "state": "pending",
        "downloaded_bytes": 0,
        "total_bytes": 100,
        "bytes_per_second": 0.0,
        "seconds_remaining": None,
        "error": None,
    }
    assert is_download_active("org/model")

    update_download("org/model", downloaded_bytes=40, bytes_per_second=10.0, seconds_remaining=6.0)
    entry = get_download("org/model")
    assert entry is not None
    assert (entry["state"], entry["downloaded_bytes"], entry["total_bytes"]) == ("downloading", 40, 100)

    finish_download("org/model")
    assert get_download("org/model") is None
    assert not is_download_active("org/model")


def test_failed_download_stays_until_the_next_attempt_and_is_not_active() -> None:
    begin_download("org/model", 100)
    update_download("org/model", downloaded_bytes=40, bytes_per_second=10.0)

    fail_download("org/model", "network down")
    finish_download("org/model")

    entry = get_download("org/model")
    assert entry is not None
    assert (entry["state"], entry["error"], entry["downloaded_bytes"], entry["bytes_per_second"]) == ("failed", "network down", 40, 0.0)
    assert not is_download_active("org/model")

    begin_download("org/model", None)
    entry = get_download("org/model")
    assert entry is not None
    assert (entry["state"], entry["error"]) == ("pending", None)
