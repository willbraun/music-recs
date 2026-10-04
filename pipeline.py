import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

from appdb import AppDb
from cache import Cache
from fetch import fetch_tracks


def run(query: str, count: int, cache: Cache, appdb: AppDb) -> Iterator[dict]:
    """Find and analyze new tracks for `query`, yielding a progress event dict per step."""
    # Heavy imports are deferred so --help and server startup stay fast.
    from analyze import analyze
    from recommend import verdict

    taste_version, taste = appdb.current_taste()
    skip_ids = cache.seen_ids() | appdb.rated_ids()
    yield {"type": "started", "query": query, "count": count, "taste_version": taste_version}

    analyzed = 0
    recommended = 0
    with tempfile.TemporaryDirectory(prefix="music-recs-") as workdir, ThreadPoolExecutor(max_workers=1) as pool:
        tracks = fetch_tracks(query, count, skip_ids, Path(workdir))
        # Download the next clip while the current one is being analyzed.
        pending = pool.submit(next, tracks, None)
        while (track := pending.result()) is not None:
            pending = pool.submit(next, tracks, None)
            analyzed += 1
            song = {"video_id": track.video_id, "title": track.title, "artist": track.artist, "url": track.url}
            yield {"type": "analyzing", "index": analyzed, **song}

            description = analyze(track.clip_path, taste)
            track.clip_path.unlink(missing_ok=True)
            is_recommended = verdict(description)
            if is_recommended is None:
                continue
            cache.add(track.video_id, track.title, track.artist, track.url, description, query, taste_version)

            recommended += is_recommended
            yield {
                "type": "scored",
                "index": analyzed,
                **song,
                "description": description,
                "recommended": is_recommended,
            }

    yield {"type": "done", "analyzed": analyzed, "recommended": recommended}
