import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import quote_plus

import yt_dlp
from yt_dlp.utils import DownloadError

CLIP_SECONDS = 60
MIN_DURATION = 90
MAX_DURATION = 480
MIN_VIEWS = 1000
OVERFETCH = 3

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
    metadata = " ".join(
        [info.get("title") or "", info.get("description") or "", info.get("uploader") or "", *(info.get("tags") or [])]
    )
    if AI_GENERATED.search(metadata):
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
    return [e for e in info["entries"] if not NON_STUDIO.search(_get_qualifiers(e.get("title") or ""))]


def _select_middle_clip(info: dict, _ydl) -> list[dict]:
    start = max(0, (info["duration"] - CLIP_SECONDS) / 2)
    return [{"start_time": start, "end_time": start + CLIP_SECONDS}]


def fetch_songs(query: str, count: int, skip_ids: set[str], workdir: Path) -> Iterator[Song]:
    """Yield up to `count` new studio songs as downloaded audio clips; skips ids in `skip_ids`."""
    candidates = [e for e in _search(query, count * OVERFETCH) if e["id"] not in skip_ids]

    opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": str(workdir / "%(id)s.%(ext)s"),
        "download_ranges": _select_middle_clip,
        "force_keyframes_at_cuts": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }
    yielded = 0
    with yt_dlp.YoutubeDL(opts) as ydl:
        for entry in candidates:
            if yielded >= count:
                return
            url = f"https://www.youtube.com/watch?v={entry['id']}"
            try:
                info = ydl.extract_info(url, download=False)
                if not _is_studio(info):
                    continue
                ydl.process_ie_result(info, download=True)
            except DownloadError as e:
                print(f"Skipping {entry['id']}: {e}")
                continue
            yielded += 1
            yield Song(info["id"], info["track"], info["artist"], url, workdir / f"{info['id']}.wav")
