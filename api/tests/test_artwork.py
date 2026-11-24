import io
import json
from urllib.error import HTTPError, URLError

import artwork
import pytest
from artwork import SongArtwork


def _recording(
    title: str = "Everything In Its Right Place",
    score: int = 100,
    groups: list[tuple[str, str | None, list[str]]] | None = None,
    id: str = "rec1",
) -> dict:
    groups = [("rg1", "Album", [])] if groups is None else groups
    return {
        "id": id,
        "score": score,
        "title": title,
        "releases": [
            {"id": f"rel-{gid}", "release-group": {"id": gid, "title": f"Title {gid}", "primary-type": primary, "secondary-types": secondary}}
            for gid, primary, secondary in groups
        ],
    }


def test_get_thumbnail_url_is_built_from_the_video_id() -> None:
    assert artwork.get_thumbnail_url("abc") == "https://img.youtube.com/vi/abc/hqdefault.jpg"


def test_get_cover_art_url_is_built_from_the_release_group_id() -> None:
    assert artwork.get_cover_art_url("rg1") == "https://coverartarchive.org/release-group/rg1/front-500"


def test_build_recording_query_escapes_special_characters_and_quotes() -> None:
    query = artwork.build_recording_query('AC/DC "Live"', "What (Is) Love?")

    assert query == r'artist:"AC\/DC \"Live\"" AND recording:"What \(Is\) Love\?" AND status:official'


def test_normalize_title_ignores_case_punctuation_and_whitespace() -> None:
    assert artwork.normalize_title("  Everything In Its Right-Place! ") == artwork.normalize_title("everything in its rightplace")


def test_pick_match_requires_a_high_score() -> None:
    assert artwork.pick_match([_recording(score=89)], "Everything In Its Right Place") is None
    assert artwork.pick_match([_recording(score=90)], "Everything In Its Right Place") is not None


def test_pick_match_requires_the_same_title() -> None:
    assert artwork.pick_match([_recording(title="Idioteque")], "Everything In Its Right Place") is None


def test_pick_match_requires_a_release_group() -> None:
    assert artwork.pick_match([_recording(groups=[])], "Everything In Its Right Place") is None


def test_pick_match_takes_the_first_qualifying_recording() -> None:
    recordings = [_recording(score=50, id="low"), _recording(groups=[], id="empty"), _recording(id="first"), _recording(id="second")]

    recording, _ = artwork.pick_match(recordings, "Everything In Its Right Place")

    assert recording["id"] == "first"


def test_pick_match_prefers_a_studio_release_group_over_an_earlier_live_one() -> None:
    recordings = [
        _recording(id="live", groups=[("live", "Album", ["Live"])]),
        _recording(id="studio", groups=[("studio", "Album", [])]),
    ]

    recording, group = artwork.pick_match(recordings, "Everything In Its Right Place")

    assert (recording["id"], group["id"]) == ("studio", "studio")


@pytest.mark.parametrize(
    ("groups", "expected"),
    [
        ([("single", "Single", []), ("ep", "EP", []), ("album", "Album", [])], "album"),
        ([("single", "Single", []), ("ep", "EP", [])], "ep"),
        ([("live", "Album", ["Live"]), ("single", "Single", [])], "single"),
        ([("comp", "Album", ["Compilation"]), ("other", "Broadcast", [])], "other"),
        ([("live", "Album", ["Live"]), ("remix", "Single", ["Remix"])], "live"),
    ],
)
def test_choose_release_group_prefers_album_then_ep_then_single(groups: list, expected: str) -> None:
    assert artwork.choose_release_group(_recording(groups=groups))["id"] == expected


def _release_group(id: str = "rg1", title: str = "Currents", score: int = 100, primary: str = "Album", secondary: list[str] | None = None) -> dict:
    return {"id": id, "title": title, "score": score, "primary-type": primary, "secondary-types": secondary or []}


@pytest.mark.parametrize(
    ("youtube_album", "musicbrainz_title"),
    [
        ("Currents", "currents"),
        ("Bangarang EP", "Bangarang"),
        ("Drink the Sea (10 Year Anniversary Deluxe Edition)", "Drink the Sea"),
    ],
)
def test_pick_release_group_matches_the_album_ignoring_editions(youtube_album: str, musicbrainz_title: str) -> None:
    assert artwork.pick_release_group([_release_group(title=musicbrainz_title)], youtube_album) is not None


def test_pick_release_group_requires_the_same_album_and_a_high_score() -> None:
    assert artwork.pick_release_group([_release_group(title="Lonerism")], "Currents") is None
    assert artwork.pick_release_group([_release_group(score=89)], "Currents") is None


def test_pick_release_group_prefers_a_studio_group_over_an_earlier_live_one() -> None:
    groups = [_release_group("live", secondary=["Live"]), _release_group("studio")]

    assert artwork.pick_release_group(groups, "Currents")["id"] == "studio"


class _Response(io.BytesIO):
    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args) -> None:
        self.close()


@pytest.fixture
def network(monkeypatch: pytest.MonkeyPatch):
    """Replaces urlopen; `routes` maps a URL prefix to a response body, or an exception to raise."""
    calls: list = []
    routes: dict = {}

    def fake_urlopen(request, timeout=None):
        calls.append((request.get_method(), request.full_url, request.get_header("User-agent"), timeout))
        for prefix, outcome in routes.items():
            if request.full_url.startswith(prefix):
                if isinstance(outcome, list):
                    outcome = outcome.pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return _Response(json.dumps(outcome).encode())
        raise AssertionError(f"Unexpected request: {request.full_url}")

    monkeypatch.setattr(artwork, "urlopen", fake_urlopen)
    monkeypatch.setattr(artwork._musicbrainz_limiter, "wait", lambda: None)
    return calls, routes


MUSICBRAINZ = artwork.MUSICBRAINZ_URL
COVER = "https://coverartarchive.org/release-group/rg1/front-500"
THUMBNAIL = "https://img.youtube.com/vi/vid/hqdefault.jpg"


def _find() -> SongArtwork:
    return artwork.find_artwork("vid", "Radiohead", "Everything In Its Right Place")


def test_find_artwork_returns_album_art_and_ids(network) -> None:
    calls, routes = network
    routes[MUSICBRAINZ] = {"recordings": [_recording()]}
    routes[COVER] = {}

    result = _find()

    assert result == SongArtwork(THUMBNAIL, COVER, "Title rg1", "rec1", "rg1")
    assert [call[0] for call in calls] == ["GET", "HEAD"]
    assert all(call[2] == artwork.USER_AGENT and call[3] == artwork.REQUEST_TIMEOUT for call in calls)
    assert "limit=25" in calls[0][1] and "fmt=json" in calls[0][1]


def test_find_artwork_keeps_ids_when_the_cover_art_is_missing(network) -> None:
    _, routes = network
    routes[MUSICBRAINZ] = {"recordings": [_recording()]}
    routes[COVER] = HTTPError(COVER, 404, "Not Found", {}, None)

    assert _find() == SongArtwork(THUMBNAIL, None, "Title rg1", "rec1", "rg1")


def test_find_artwork_without_a_match_has_only_the_thumbnail(network) -> None:
    _, routes = network
    routes[MUSICBRAINZ] = {"recordings": [_recording(score=40)]}

    assert _find() == SongArtwork(THUMBNAIL)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        URLError("offline"),
        HTTPError(MUSICBRAINZ, 503, "Service Unavailable", {}, None),
        HTTPError(MUSICBRAINZ, 500, "Server Error", {}, None),
    ],
)
def test_find_artwork_treats_musicbrainz_failures_as_no_match(network, error: Exception) -> None:
    _, routes = network
    routes[MUSICBRAINZ] = error

    assert _find() == SongArtwork(THUMBNAIL)


def test_find_artwork_retries_a_musicbrainz_503(network) -> None:
    calls, routes = network
    routes[MUSICBRAINZ] = [HTTPError(MUSICBRAINZ, 503, "Busy", {}, None), {"recordings": [_recording()]}]
    routes[COVER] = {}

    assert _find().album == "Title rg1"
    assert [call[0] for call in calls] == ["GET", "GET", "HEAD"]


def test_find_artwork_gives_up_after_repeated_503s(network) -> None:
    calls, routes = network
    routes[MUSICBRAINZ] = HTTPError(MUSICBRAINZ, 503, "Busy", {}, None)

    assert _find() == SongArtwork(THUMBNAIL)
    assert len(calls) == artwork.MUSICBRAINZ_ATTEMPTS


def test_find_artwork_treats_a_cover_art_server_error_as_no_match(network) -> None:
    _, routes = network
    routes[MUSICBRAINZ] = {"recordings": [_recording()]}
    routes[COVER] = HTTPError(COVER, 503, "Service Unavailable", {}, None)

    assert _find() == SongArtwork(THUMBNAIL)


def test_find_artwork_treats_an_invalid_response_as_no_match(network, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(artwork, "_get_json", lambda url: json.loads("{"))

    assert artwork.find_artwork("vid", "A", "T") == SongArtwork(THUMBNAIL)


RELEASE_GROUP = artwork.RELEASE_GROUP_URL


def _find_with_album() -> SongArtwork:
    return artwork.find_artwork("vid", "Tame Impala, Someone", "Let It Happen", "Currents", "Tame Impala")


def test_find_artwork_with_a_youtube_album_only_looks_up_its_cover(network) -> None:
    calls, routes = network
    routes[RELEASE_GROUP] = {"release-groups": [_release_group()]}
    routes[COVER] = {}

    assert _find_with_album() == SongArtwork(THUMBNAIL, COVER, "Currents", None, "rg1")
    assert [call[1].split("?")[0] for call in calls] == [RELEASE_GROUP, COVER]
    assert 'artist%3A%22Tame%20Impala%22' in calls[0][1]


def test_find_artwork_searches_the_album_by_a_lead_artist_containing_a_comma(network) -> None:
    calls, routes = network
    routes[RELEASE_GROUP] = {"release-groups": [_release_group(title="IGOR")]}
    routes[COVER] = {}

    artwork.find_artwork("vid", "Tyler, The Creator, Kanye West", "EARFQUAKE", "IGOR", "Tyler, The Creator")

    assert "artist%3A%22Tyler%2C%20The%20Creator%22" in calls[0][1]


def test_find_artwork_with_a_youtube_album_searches_without_the_edition(network) -> None:
    calls, routes = network
    routes[RELEASE_GROUP] = {"release-groups": [_release_group(title="Bangarang")]}
    routes[COVER] = {}

    result = artwork.find_artwork("vid", "Skrillex, Sirah", "Bangarang", "Bangarang (Deluxe) EP")

    assert result.album == "Bangarang (Deluxe) EP"
    assert "releasegroup%3A%22Bangarang%22" in calls[0][1]


def test_find_artwork_without_a_release_group_falls_back_to_the_recording_and_keeps_the_youtube_album(network) -> None:
    calls, routes = network
    routes[RELEASE_GROUP] = {"release-groups": [_release_group(title="Lonerism")]}
    routes[MUSICBRAINZ] = {"recordings": [_recording(title="Let It Happen")]}
    routes[COVER] = {}

    assert _find_with_album() == SongArtwork(THUMBNAIL, COVER, "Currents", "rec1", "rg1")
    assert [call[1].split("?")[0] for call in calls] == [RELEASE_GROUP, MUSICBRAINZ, COVER]


def test_find_artwork_with_no_release_group_or_recording_keeps_the_youtube_album(network) -> None:
    _, routes = network
    routes[RELEASE_GROUP] = {"release-groups": []}
    routes[MUSICBRAINZ] = {"recordings": []}

    assert _find_with_album() == SongArtwork(THUMBNAIL, album="Currents")


def test_find_artwork_with_a_youtube_album_keeps_it_when_musicbrainz_fails(network) -> None:
    _, routes = network
    routes[RELEASE_GROUP] = HTTPError(RELEASE_GROUP, 503, "Busy", {}, None)

    assert _find_with_album() == SongArtwork(THUMBNAIL, album="Currents")


def test_find_artwork_with_a_youtube_album_keeps_it_when_the_cover_is_missing(network) -> None:
    _, routes = network
    routes[RELEASE_GROUP] = {"release-groups": [_release_group()]}
    routes[COVER] = HTTPError(COVER, 404, "Not Found", {}, None)

    assert _find_with_album() == SongArtwork(THUMBNAIL, None, "Currents", None, "rg1")


def test_rate_limiter_waits_between_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [100.0]
    sleeps: list[float] = []
    monkeypatch.setattr(artwork.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(artwork.time, "sleep", lambda seconds: (sleeps.append(seconds), now.__setitem__(0, now[0] + seconds)))
    limiter = artwork._RateLimiter(1.0)

    limiter.wait()
    now[0] += 0.4
    limiter.wait()

    assert sleeps == [pytest.approx(0.6)]
