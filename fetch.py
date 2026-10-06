import re
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import quote_plus

import yt_dlp
from yt_dlp.utils import DownloadError

CLIP_SECONDS = 45
MIN_DURATION = 90
MAX_DURATION = 480
MIN_VIEWS = 1000
OVERFETCH = 3
DOWNLOAD_WORKERS = 4
DOWNLOAD_ATTEMPTS = 3

NON_STUDIO = re.compile(
    r"\b(live|remix(es)?|rmx|cover|acoustic|karaoke|instrumental|sped up|slowed|reverb|mix|session|"
    r"version|podcast|mashup|nightcore|8d)\b",
    re.IGNORECASE,
)

AI_GENERATED = re.compile(
    r"\b(suno|udio|(ai|artificial intelligence)[- ](generated|made|music|created|vocals?|voice)|"
    r"(generated|made|created|composed|produced) (with|by|using) (ai|suno|udio))\b",
    re.IGNORECASE,
)


@dataclass
class Song:
    video_id: str
    title: str
    artist: str
    url: str
    clip_path: Path


def _get_qualifiers(title: str) -> str:
    # Only brackets and dash suffixes, so titles like "Live Forever" survive.
    return " ".join(re.findall(r"[(\[]([^)\]]*)[)\]]", title) + title.split(" - ")[1:])


def _is_studio(info: dict) -> bool:
    title = info.get("track") or ""
    artist = info.get("artist") or ""
    if not title or not artist:
        return False
    if not MIN_DURATION <= (info.get("duration") or 0) <= MAX_DURATION:
        return False
    if (info.get("view_count") or 0) < MIN_VIEWS:
        return False
    tags = info.get("tags") or []
    metadata = " ".join([info.get("title") or "", info.get("description") or "", info.get("uploader") or "", *tags])
    if AI_GENERATED.search(metadata) or any(tag.strip().casefold() == "ai" for tag in tags):
        return False
    return not (
        NON_STUDIO.search(_get_qualifiers(info.get("title") or ""))
        or NON_STUDIO.search(_get_qualifiers(title))
        or NON_STUDIO.search(info.get("album") or "")
    )


def _search(query: str, limit: int) -> list[dict]:
    url = f"https://music.youtube.com/search?q={quote_plus(query)}#songs"
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist", "playlistend": limit}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    # Flat entries only carry id/title/url, so title is the only pre-fetch filter.
    return [
        e
        for e in info["entries"]
        if not NON_STUDIO.search(_get_qualifiers(e.get("title") or ""))
        and not AI_GENERATED.search(e.get("title") or "")
    ]


def _select_middle_clip(info: dict, _ydl) -> list[dict]:
    start = max(0, (info["duration"] - CLIP_SECONDS) / 2)
    return [{"start_time": start, "end_time": start + CLIP_SECONDS}]


def _download_song(video_id: str, workdir: Path) -> Song | None:
    """Fetch metadata and, for studio songs, download the clip; None if rejected or failed."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "download_ranges": _select_middle_clip,
        "force_keyframes_at_cuts": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    for attempt in range(DOWNLOAD_ATTEMPTS):
        try:
            # YoutubeDL instances aren't thread-safe, so each task gets its own.
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not _is_studio(info):
                    return None
                ydl.process_ie_result(info, download=True)
            break
        except DownloadError as e:
            # ffmpeg fails sporadically (HTTP errors on the stream URL); a fresh extraction usually fixes it.
            if attempt == DOWNLOAD_ATTEMPTS - 1:
                print(f"Skipping {video_id}: {e}")
                return None
    return Song(info["id"], info["track"], info["artist"], url, workdir / f"{info['id']}.wav")


def fetch_songs(
    query: str, count: int, skip_ids: set[str], workdir: Path
) -> Iterator[Song]:
    """Yield up to `count` studio-song audio clips; record considered ids in `skip_ids`.

    Up to DOWNLOAD_WORKERS candidates are fetched ahead of the consumer, in search order.
    """
    candidates = iter([e for e in _search(query, count * OVERFETCH) if e["id"] not in skip_ids])
    pending: deque[Future[Song | None]] = deque()
    yielded = 0
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        try:
            while yielded < count:
                while len(pending) < DOWNLOAD_WORKERS and (entry := next(candidates, None)):
                    skip_ids.add(entry["id"])
                    pending.append(pool.submit(_download_song, entry["id"], workdir))
                if not pending:
                    return
                song = pending.popleft().result()
                if song is None:
                    continue
                yielded += 1
                yield song
        finally:
            for future in pending:
                future.cancel()
