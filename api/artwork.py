import json
import logging
import re
import threading
import time
from dataclasses import dataclass
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# MusicBrainz asks every client to identify itself. Set the contact to your own address.
APP_VERSION = "0.1"
CONTACT = "williamhbraun1@gmail.com"
USER_AGENT = f"music-recs/{APP_VERSION} ({CONTACT})"

MUSICBRAINZ_URL = "https://musicbrainz.org/ws/2/recording/"
COVER_ART_URL = "https://coverartarchive.org/release-group/{}/front-500"
THUMBNAIL_URL = "https://img.youtube.com/vi/{}/hqdefault.jpg"

MIN_SCORE = 90
SEARCH_LIMIT = 25
REQUEST_TIMEOUT = 5
MUSICBRAINZ_INTERVAL = 1.0
MUSICBRAINZ_ATTEMPTS = 3

PRIMARY_TYPE_RANK = {"Album": 0, "EP": 1, "Single": 2}
EXCLUDED_SECONDARY_TYPES = {"Compilation", "Live", "Soundtrack", "Remix"}


@dataclass(frozen=True)
class SongArtwork:
    thumbnail_url: str
    album_art_url: str | None = None
    album: str | None = None
    recording_id: str | None = None
    release_group_id: str | None = None


class _RateLimiter:
    """Spaces calls at least `interval` seconds apart across threads."""

    def __init__(self, interval: float):
        self._interval = interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            delay = self._last + self._interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


_musicbrainz_limiter = _RateLimiter(MUSICBRAINZ_INTERVAL)


def get_thumbnail_url(video_id: str) -> str:
    return THUMBNAIL_URL.format(video_id)


def get_cover_art_url(release_group_id: str) -> str:
    return COVER_ART_URL.format(release_group_id)


def escape_query_value(value: str) -> str:
    """Escape a value for use inside a double-quoted Lucene phrase."""
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", value)


def normalize_title(title: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", "", title.casefold()).split())


def build_recording_query(artist: str, title: str) -> str:
    # status:official drops bootleg live recordings that otherwise crowd out the studio release.
    return f'artist:"{escape_query_value(artist)}" AND recording:"{escape_query_value(title)}" AND status:official'


def _rank_release_group(group: dict) -> tuple[int, int]:
    excluded = EXCLUDED_SECONDARY_TYPES.intersection(group.get("secondary-types") or [])
    return (1 if excluded else 0, PRIMARY_TYPE_RANK.get(group.get("primary-type"), len(PRIMARY_TYPE_RANK)))


def choose_release_group(recording: dict) -> dict | None:
    groups = [r["release-group"] for r in recording.get("releases") or [] if r.get("release-group")]
    # min keeps the first of equally ranked groups.
    return min(groups, key=_rank_release_group, default=None)


def pick_match(recordings: list[dict], title: str) -> tuple[dict, dict] | None:
    """Return the confident recording and release group with the best group rank, or None."""
    wanted = normalize_title(title)
    candidates = []
    for recording in recordings:
        if recording.get("score", 0) < MIN_SCORE or normalize_title(recording.get("title", "")) != wanted:
            continue
        group = choose_release_group(recording)
        if group:
            candidates.append((recording, group))
    # Live and compilation recordings often rank first, so compare groups across recordings; min keeps search order on ties.
    return min(candidates, key=lambda c: _rank_release_group(c[1]), default=None)


def _get_json(url: str) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(MUSICBRAINZ_ATTEMPTS):
        _musicbrainz_limiter.wait()
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return json.load(response)
        except HTTPError as e:
            # MusicBrainz sheds load with 503s that usually clear on the next try.
            if e.code != 503 or attempt == MUSICBRAINZ_ATTEMPTS - 1:
                raise
    raise AssertionError("unreachable")


def _has_cover_art(url: str) -> bool:
    """HEAD the Cover Art Archive URL; a 404 means there is no front cover."""
    request = Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT):
            return True
    except HTTPError as e:
        if e.code == 404:
            return False
        raise


def find_recording(artist: str, title: str) -> tuple[dict, dict] | None:
    params = urlencode({"query": build_recording_query(artist, title), "fmt": "json", "limit": SEARCH_LIMIT}, quote_via=quote)
    return pick_match(_get_json(f"{MUSICBRAINZ_URL}?{params}").get("recordings") or [], title)


def find_artwork(video_id: str, artist: str, title: str) -> SongArtwork:
    """Look up the album art for a song; any failure leaves only the YouTube thumbnail."""
    thumbnail = SongArtwork(get_thumbnail_url(video_id))
    try:
        match = find_recording(artist, title)
        if match is None:
            return thumbnail
        recording, group = match
        art_url = get_cover_art_url(group["id"])
        return SongArtwork(
            thumbnail_url=thumbnail.thumbnail_url,
            album_art_url=art_url if _has_cover_art(art_url) else None,
            album=group.get("title"),
            recording_id=recording["id"],
            release_group_id=group["id"],
        )
    except (OSError, ValueError, KeyError, HTTPException) as e:
        logger.warning("Artwork lookup failed for %s - %s: %s", artist, title, e)
        return thumbnail
