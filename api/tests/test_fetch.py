from pathlib import Path

import fetch
import pytest
from fetch import Song, fetch_songs
from yt_dlp.utils import DownloadError


def _info(**overrides) -> dict:
    info = {
        "id": "abc",
        "track": "Song",
        "artist": "Artist",
        "title": "Artist - Song",
        "duration": 200,
        "view_count": 5000,
        "tags": [],
        "album": "Album",
    }
    return {**info, **overrides}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Song (Live at Wembley) [Remastered]", "Live at Wembley Remastered"),
        ("Song - Remix", "Remix"),
        ("Live Forever", ""),
    ],
)
def test_get_qualifiers_only_reads_brackets_and_dash_suffixes(title: str, expected: str) -> None:
    assert fetch._get_qualifiers(title) == expected


def test_is_studio_accepts_a_normal_song() -> None:
    assert fetch._is_studio(_info())


@pytest.mark.parametrize(
    "overrides",
    [
        {"track": ""},
        {"artist": None},
        {"duration": 30},
        {"duration": 900},
        {"duration": None},
        {"view_count": 10},
        {"title": "Artist - Song (Live)"},
        {"track": "Song (Acoustic)"},
        {"album": "Greatest Remixes"},
        {"description": "Made with Suno"},
        {"tags": ["AI"]},
        {"uploader": "AI generated music"},
    ],
)
def test_is_studio_rejects(overrides: dict) -> None:
    assert not fetch._is_studio(_info(**overrides))


class _FakeYoutubeDL:
    def __init__(self, opts: dict, info: dict | None = None, fail_times: int = 0) -> None:
        self.opts = opts
        self.info = info
        self.fail_times = fail_times
        self.downloaded = False

    def __enter__(self):
        return self

    def __exit__(self, *_exc) -> None:
        return None

    def extract_info(self, url: str, download: bool):
        if self.fail_times:
            self.fail_times -= 1
            raise DownloadError("boom")
        return self.info

    def process_ie_result(self, info: dict, download: bool) -> None:
        self.downloaded = True


def test_search_filters_non_studio_and_ai_titles(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        {"id": "1", "title": "Good Song"},
        {"id": "2", "title": "Song (Live)"},
        {"id": "3", "title": "Suno generated"},
    ]
    seen: dict = {}

    def make_ydl(opts: dict) -> _FakeYoutubeDL:
        seen["opts"] = opts
        return _FakeYoutubeDL(opts, {"entries": entries})

    monkeypatch.setattr(fetch.yt_dlp, "YoutubeDL", make_ydl)

    assert fetch._search("a b", 9) == [entries[0]]
    assert seen["opts"]["playlistend"] == 9


def test_select_middle_clip_centers_the_clip() -> None:
    assert fetch._select_middle_clip({"duration": 200}, None) == [{"start_time": 77.5, "end_time": 122.5}]


def test_select_middle_clip_starts_at_zero_for_short_tracks() -> None:
    assert fetch._select_middle_clip({"duration": 10}, None)[0]["start_time"] == 0


def test_download_song_returns_song_for_studio_track(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ydl = _FakeYoutubeDL({}, _info())
    monkeypatch.setattr(fetch.yt_dlp, "YoutubeDL", lambda opts: ydl)

    song = fetch._download_song("abc", tmp_path)

    assert song == Song("abc", "Song", "Artist", "https://www.youtube.com/watch?v=abc", tmp_path / "abc.wav")
    assert ydl.downloaded


def test_download_song_skips_non_studio_without_downloading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ydl = _FakeYoutubeDL({}, _info(duration=10))
    monkeypatch.setattr(fetch.yt_dlp, "YoutubeDL", lambda opts: ydl)

    assert fetch._download_song("abc", tmp_path) is None
    assert not ydl.downloaded


def test_download_song_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ydl = _FakeYoutubeDL({}, _info(), fail_times=fetch.DOWNLOAD_ATTEMPTS - 1)
    monkeypatch.setattr(fetch.yt_dlp, "YoutubeDL", lambda opts: ydl)

    assert fetch._download_song("abc", tmp_path) is not None


def test_download_song_gives_up_after_all_attempts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ydl = _FakeYoutubeDL({}, _info(), fail_times=fetch.DOWNLOAD_ATTEMPTS)
    monkeypatch.setattr(fetch.yt_dlp, "YoutubeDL", lambda opts: ydl)

    assert fetch._download_song("abc", tmp_path) is None


def _stub_fetching(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, ids: list[str], rejected: set[str] = frozenset()) -> None:
    monkeypatch.setattr(fetch, "_search", lambda query, limit: [{"id": i} for i in ids])
    monkeypatch.setattr(
        fetch,
        "_download_song",
        lambda video_id, workdir: None if video_id in rejected else Song(video_id, "t", "a", "u", tmp_path / video_id),
    )


def test_fetch_songs_yields_up_to_count_in_search_order(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_fetching(monkeypatch, tmp_path, ["a", "b", "c", "d"])

    songs = list(fetch_songs("q", 2, set(), tmp_path))

    assert [s.video_id for s in songs] == ["a", "b"]


def test_fetch_songs_skips_known_and_rejected_ids(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_fetching(monkeypatch, tmp_path, ["a", "b", "c", "d"], rejected={"c"})
    skip_ids = {"a"}

    songs = list(fetch_songs("q", 3, skip_ids, tmp_path))

    assert [s.video_id for s in songs] == ["b", "d"]
    # Every considered id is recorded so later searches don't repeat it.
    assert {"a", "b", "c", "d"} <= skip_ids


def test_fetch_songs_returns_nothing_when_no_candidates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_fetching(monkeypatch, tmp_path, [])

    assert list(fetch_songs("q", 2, set(), tmp_path)) == []
