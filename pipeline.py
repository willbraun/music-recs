import math
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

from appdb import AppDb
from cache import Cache
from fetch import OVERFETCH, Song, fetch_songs

MAX_QUERIES = 6
CANDIDATES_PER_RECOMMENDATION = 2
MAX_SEARCH_RESULTS_PER_QUERY = 300


def _find_songs(
    searches: list[tuple[str, str | None]],
    count: int,
    skip_ids: set[str],
    workdir: Path,
) -> Iterator[tuple[Song, str, str | None]]:
    """Yield songs in expanding batches, up to the per-query search result limit."""
    max_count = MAX_SEARCH_RESULTS_PER_QUERY // OVERFETCH * len(searches)
    count = min(count, max_count)
    while count:
        remaining = count
        for i, (query, tier) in enumerate(searches):
            if remaining == 0:
                break
            share = math.ceil(remaining / (len(searches) - i))
            for song in fetch_songs(query, share, skip_ids, workdir):
                # Later queries and batches must not return this song again.
                skip_ids.add(song.video_id)
                remaining -= 1
                yield song, query, tier
        if count == max_count:
            return
        count = min(count * 2, max_count)


def run(
    query: str | None,
    count: int,
    exploration: int,
    cache: Cache,
    appdb: AppDb,
) -> Iterator[dict]:
    """Find and analyze new songs, yielding a progress event dict per step.

    Without a `query`, search queries are generated from the taste at the given `exploration` level (0-100).
    """
    # Heavy imports are deferred so --help and server startup stay fast.
    from analyze import analyze
    from queries import generate_queries
    from recommend import get_verdict

    # 1. Load the current taste and the ids that must not be recommended again.
    taste_version, taste = appdb.get_current_taste()
    skip_ids = cache.get_seen_ids() | appdb.get_rated_ids()
    yield {"type": "started", "query": query, "count": count, "exploration": exploration, "taste_version": taste_version}

    # 2. Use the given query, or generate queries from the taste at this exploration level.
    candidate_limit = count * CANDIDATES_PER_RECOMMENDATION
    if query is None:
        generated = generate_queries(taste, exploration, min(candidate_limit, MAX_QUERIES))
        searches = [(g.query, g.tier) for g in generated]
        yield {"type": "queries", "queries": [{"query": q, "tier": tier} for q, tier in searches]}
    else:
        searches = [(query, None)]

    # 3. Download clips for each query and analyze them one at a time.
    yield {"type": "fetching"}
    analyzed = 0
    recommended = 0
    with tempfile.TemporaryDirectory(prefix="music-recs-") as workdir, ThreadPoolExecutor(max_workers=1) as pool:
        songs = _find_songs(searches, candidate_limit, skip_ids, Path(workdir))
        # A single worker fetches the next clip while the current one is being analyzed.
        pending = pool.submit(next, songs, None)
        while (found := pending.result()) is not None:
            song, song_query, tier = found
            pending = pool.submit(next, songs, None)
            analyzed += 1
            result = {
                "video_id": song.video_id,
                "title": song.title,
                "artist": song.artist,
                "url": song.url,
                "query": song_query,
                "tier": tier,
            }
            yield {
                "type": "analyzing",
                "index": analyzed,
                "recommended_count": recommended,
                **result,
            }

            # 4. Ask the audio model for a verdict; analyses without one are dropped.
            description = analyze(song.clip_path, taste, exploration)
            song.clip_path.unlink(missing_ok=True)
            is_recommended = get_verdict(description)
            if is_recommended is None:
                continue

            # 5. Cache the song so later runs skip it, then report the result.
            cache.add(song.video_id, song.title, song.artist, song.url, description, song_query, taste_version)

            recommended += is_recommended
            yield {
                "type": "scored",
                "index": analyzed,
                **result,
                "description": description,
                "recommended": is_recommended,
            }
            if recommended >= count:
                break

    yield {"type": "done", "analyzed": analyzed, "recommended": recommended, "count": count}
