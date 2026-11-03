import threading
from types import SimpleNamespace

import model_download
import pytest
from model_download import (RECONSTRUCT_BAR_NAME, TRANSFER_BAR_NAME,
                            _SpeedWindow, download_model, get_download_size)


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
    release = threading.Event()

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
    release = threading.Event()

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
    release = threading.Event()
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
    release = threading.Event()

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


def test_speed_window_averages_over_the_recent_window() -> None:
    window = _SpeedWindow(0.0)

    assert window.update(1.0, 100) == 100
    assert window.update(2.0, 300) == 150
    # Samples older than the window drop out: from t=2 (300 bytes) to t=8 (900 bytes).
    assert window.update(8.0, 900) == pytest.approx(100)


def test_speed_window_is_zero_without_progress() -> None:
    window = _SpeedWindow(0.0)

    assert window.update(1.0, 0) == 0
