import math
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

from appdb import AppDb, get_artist_key
from artwork import find_artwork
from fetch import OVERFETCH, Song, fetch_songs

MAX_QUERIES = 6
CANDIDATES_PER_RECOMMENDATION = 2
MAX_SEARCH_RESULTS_PER_QUERY = 300
FREQUENT_ARTIST_RECOMMENDATIONS = 3
FREQUENT_ARTIST_WINDOW = 100
NO_TASTE_MESSAGE = "Set your taste first"


def _find_songs(
    searches: list[tuple[str, str | None]],
    count: int,
    skip_ids: set[str],
    workdir: Path,
    avoid_artists: frozenset[str] | set[str] = frozenset(),
) -> Iterator[tuple[Song, str, str | None]]:
    """Yield songs in expanding batches, up to the per-query search result limit. Each artist appears once.

    Songs by `avoid_artists` (artist keys) are held back and yielded last, only if the consumer still wants more.
    """
    max_count = MAX_SEARCH_RESULTS_PER_QUERY // OVERFETCH * len(searches)
    count = min(count, max_count)
    seen_artists: set[str] = set()
    deferred: list[tuple[Song, str, str | None]] = []
    while count:
        remaining = count
        for i, (query, tier) in enumerate(searches):
            if remaining == 0:
                break
            share = math.ceil(remaining / (len(searches) - i))
            for song in fetch_songs(query, share, skip_ids, workdir):
                # Later queries and batches must not return this song again.
                skip_ids.add(song.video_id)

                # Skip songs by artists already seen anywhere in this run.
                artist_key = get_artist_key(song.artist)
                if artist_key in seen_artists:
                    song.clip_path.unlink(missing_ok=True)
                    continue
                seen_artists.add(artist_key)
                if artist_key in avoid_artists:
                    deferred.append((song, query, tier))
                    continue
                remaining -= 1
                yield song, query, tier
        if count == max_count:
            break
        count = min(count * 2, max_count)
    yield from deferred


def _download_model_if_missing(model_id: str) -> Iterator[dict]:
    """Yield a downloading_model event and download the model, unless it is already cached."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        snapshot_download(model_id, local_files_only=True)
    except LocalEntryNotFoundError:
        yield {"type": "downloading_model", "model": model_id}
        snapshot_download(model_id)


def run(
    query: str | None,
    count: int,
    exploration: int,
    appdb: AppDb,
) -> Iterator[dict]:
    """Find and analyze new songs, yielding a progress event dict per step.

    Without a `query`, search queries are generated from the taste at the given `exploration` level (0-100).
    """
    # Heavy imports are deferred so --help and server startup stay fast.
    from analyze import MODEL_ID as ANALYSIS_MODEL_ID
    from analyze import analyze
    from queries import MODEL_ID as QUERY_MODEL_ID
    from queries import generate_queries

    # 1. Load the current taste and the ids that must not be recommended again.
    saved_taste = appdb.get_current_taste()
    if saved_taste is None:
        raise RuntimeError(NO_TASTE_MESSAGE)
    taste = saved_taste.text
    skip_ids = appdb.get_seen_ids()
    # Artists recommended often already are avoided so the results stay varied.
    artist_counts = appdb.get_recommended_artist_counts(FREQUENT_ARTIST_WINDOW)
    frequent_artists = [artist for artist, n in artist_counts.items() if n >= FREQUENT_ARTIST_RECOMMENDATIONS]
    yield {"type": "started", "query": query, "count": count, "exploration": exploration}

    # 2. Use the given query, or generate queries from the taste at this exploration level.
    candidate_limit = count * CANDIDATES_PER_RECOMMENDATION
    if query is None:
        yield from _download_model_if_missing(QUERY_MODEL_ID)
        generated = generate_queries(
            taste, saved_taste.profile.liked_artists, exploration, min(candidate_limit, MAX_QUERIES), frequent_artists
        )
        searches = [(g.query, g.tier) for g in generated]
        yield {"type": "queries", "queries": [{"query": q, "tier": tier} for q, tier in searches]}
    else:
        searches = [(query, None)]

    # 3. Download clips for each query and analyze them one at a time.
    yield from _download_model_if_missing(ANALYSIS_MODEL_ID)
    yield {"type": "fetching"}
    analyzed = 0
    recommended = 0
    avoid_keys = {get_artist_key(artist) for artist in frequent_artists}
    with tempfile.TemporaryDirectory(prefix="music-recs-") as workdir, ThreadPoolExecutor(max_workers=1) as pool:
        songs = _find_songs(searches, candidate_limit, skip_ids, Path(workdir), avoid_keys)
        # fetch_songs downloads several clips ahead in parallel; this thread only hands them to the analyzer.
        pending = pool.submit(next, songs, None)
        try:
            while (found := pending.result()) is not None:
                song, song_query, tier = found
                pending = pool.submit(next, songs, None)
                analyzed += 1
                # Looked up before analysis so the loading card shows the same art as the final card.
                artwork = find_artwork(song.video_id, song.artist, song.title)
                result = {
                    "video_id": song.video_id,
                    "title": song.title,
                    "artist": song.artist,
                    "url": song.url,
                    "query": song_query,
                    "tier": tier,
                    "thumbnail_url": artwork.thumbnail_url,
                    "album_art_url": artwork.album_art_url,
                }
                yield {
                    "type": "analyzing",
                    "index": analyzed,
                    "recommended_count": recommended,
                    **result,
                }

                # 4. Ask the audio model for a verdict.
                verdict = analyze(song.clip_path, taste, exploration)
                song.clip_path.unlink(missing_ok=True)

                # 5. Cache the song so later runs skip it, then report.
                appdb.add_song(
                    song.video_id,
                    song.title,
                    song.artist,
                    song.url,
                    verdict.recommended,
                    verdict.confidence,
                    song_query,
                    thumbnail_url=artwork.thumbnail_url,
                    album_art_url=artwork.album_art_url,
                    album=artwork.album,
                    musicbrainz_recording_id=artwork.recording_id,
                    musicbrainz_release_group_id=artwork.release_group_id,
                )

                recommended += verdict.recommended
                yield {
                    "type": "scored",
                    "index": analyzed,
                    **result,
                    "recommended": verdict.recommended,
                    "confidence": verdict.confidence,
                    "album": artwork.album,
                    "musicbrainz_recording_id": artwork.recording_id,
                    "musicbrainz_release_group_id": artwork.release_group_id,
                }
                if recommended >= count:
                    break
        finally:
            # Let the in-flight pull finish, then stop downloads before the workdir is deleted.
            pool.shutdown(wait=True)
            songs.close()

    yield {"type": "done", "analyzed": analyzed, "recommended": recommended, "count": count}
