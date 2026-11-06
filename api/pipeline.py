import math
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

from appdb import AppDb, get_artist_key
from artwork import find_artwork
from fetch import OVERFETCH, Song, fetch_songs
from model_download import (begin_download, download_model, fail_download,
                            finish_download, get_download_size,
                            is_model_downloaded, update_download)

# Songs and queries are over-provisioned by this factor, since the model rejects some songs.
CANDIDATES_PER_RECOMMENDATION = 2
MAX_SEARCH_RESULTS_PER_QUERY = 300
# A lead artist with this many songs among the last WINDOW recommended is avoided: queries steer away, their songs go last.
FREQUENT_ARTIST_RECOMMENDATIONS = 3
FREQUENT_ARTIST_WINDOW = 100
NO_TASTE_MESSAGE = "Set your taste first"

# (query, tier) as generated from the taste.
Search = tuple[str, str]
# (song, query that found it, tier of that query).
FoundSong = tuple[Song, str, str]


def _is_blocked(artist: str, blocked_artists: frozenset[str] | set[str]) -> bool:
    # Any credited artist counts, so a disliked guest blocks "Lead, Guest"; the whole credit covers names with a comma.
    credits = {artist.strip().casefold(), *(name.strip().casefold() for name in artist.split(","))}
    return not credits.isdisjoint(blocked_artists)


def _find_songs(
    searches: list[Search],
    count: int,
    skip_ids: set[str],
    workdir: Path,
    avoid_artists: frozenset[str] | set[str] = frozenset(),
    blocked_artists: frozenset[str] | set[str] = frozenset(),
) -> Iterator[FoundSong]:
    """Yield songs in expanding batches, up to the per-query search result limit. Each artist appears once.

    Songs by `avoid_artists` (artist keys) are held back and yielded last, only if the consumer still wants more.
    Songs crediting any of `blocked_artists` (casefolded names) are never yielded.
    """
    # Each query can be asked for at most MAX_SEARCH_RESULTS_PER_QUERY results, of which 1/OVERFETCH become songs.
    max_target = MAX_SEARCH_RESULTS_PER_QUERY // OVERFETCH * len(searches)
    target = min(count, max_target)
    seen_artists: set[str] = set()
    deferred: list[FoundSong] = []

    # Each pass asks every query for a share of `target` songs; the target doubles while the consumer keeps pulling.
    while target:
        remaining = target
        for i, (query, tier) in enumerate(searches):
            if remaining == 0:
                break
            # Split what is still missing across the queries left, so a query that comes up short is made up by later ones.
            share = math.ceil(remaining / (len(searches) - i))
            for song in fetch_songs(query, share, skip_ids, workdir):
                # Later queries and passes must not return this song again.
                skip_ids.add(song.video_id)

                if _is_blocked(song.artist, blocked_artists):
                    song.clip_path.unlink(missing_ok=True)
                    continue

                # Skip songs by artists already seen anywhere in this run.
                artist_key = get_artist_key(song.artist)
                if artist_key in seen_artists:
                    song.clip_path.unlink(missing_ok=True)
                    continue
                seen_artists.add(artist_key)

                # Held back songs do not count toward this pass's share.
                if artist_key in avoid_artists:
                    deferred.append((song, query, tier))
                    continue
                remaining -= 1
                yield song, query, tier
        if target == max_target:
            break
        target = min(target * 2, max_target)
    yield from deferred


def download_missing_models(model_ids: list[str]) -> Iterator[dict]:
    """Download the uncached models one after another, yielding nothing when all are cached.

    One downloading_models event lists every missing model with its size first. Each download is then bracketed by
    downloading_model and model_downloaded events, with download_progress events between them.

    Progress is also kept in the shared download registry, so clients that did not start the download can show it.
    """
    missing = [model_id for model_id in model_ids if not is_model_downloaded(model_id)]
    current: str | None = None
    try:
        if not missing:
            return

        sizes = {model_id: get_download_size(model_id) for model_id in missing}
        for model_id in missing:
            begin_download(model_id, sizes[model_id])
        yield {"type": "downloading_models", "models": [{"model": m, "total_bytes": sizes[m]} for m in missing]}
        for model_id in missing:
            current = model_id
            update_download(model_id)
            yield {"type": "downloading_model", "model": model_id, "total_bytes": sizes[model_id]}
            for event in download_model(model_id, sizes[model_id]):
                update_download(
                    model_id,
                    downloaded_bytes=event["downloaded_bytes"],
                    total_bytes=event["total_bytes"],
                    bytes_per_second=event["bytes_per_second"],
                    seconds_remaining=event["seconds_remaining"],
                )
                yield event
            finish_download(model_id)
            yield {"type": "model_downloaded", "model": model_id}
    except Exception as e:
        # Before the first download starts, every missing model is affected.
        for model_id in [current] if current else missing:
            fail_download(model_id, str(e))
        raise
    finally:
        # Includes cached models, whose "pending" entry may have been set by a queued Models-page download.
        for model_id in model_ids:
            finish_download(model_id)


def run(count: int, exploration: int, appdb: AppDb) -> Iterator[dict]:
    """Find and analyze new songs until `count` are recommended, yielding a progress event dict per step.

    Search queries are generated from the taste at the given `exploration` level (0-100).
    Events, in order: started, [downloading_*], queries, fetching, then analyzing/scored per song, and done.
    """
    # Heavy imports are deferred so server startup stays fast.
    from analyze import analyze
    from model_download import ANALYSIS_MODEL_ID, QUERY_MODEL_ID
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
    yield {"type": "started", "count": count, "exploration": exploration}

    # 2. Download every model this run needs now, so no later step stalls on a download.
    yield from download_missing_models([QUERY_MODEL_ID, ANALYSIS_MODEL_ID])

    # 3. Generate the search queries, one per candidate song at most, split across tiers by `exploration`.
    candidate_limit = count * CANDIDATES_PER_RECOMMENDATION
    generated = generate_queries(
        taste, saved_taste.profile.liked_artists, exploration, candidate_limit, frequent_artists
    )
    searches = [(g.query, g.tier) for g in generated]
    yield {"type": "queries", "queries": [{"query": q, "tier": tier} for q, tier in searches]}

    # 4. Download clips for each query and analyze them one at a time, stopping once enough are recommended.
    yield {"type": "fetching"}
    analyzed = 0
    recommended = 0
    avoid_keys = {get_artist_key(artist) for artist in frequent_artists}
    blocked_keys = {artist.strip().casefold() for artist in saved_taste.profile.disliked_artists}
    with tempfile.TemporaryDirectory(prefix="music-recs-") as workdir, ThreadPoolExecutor(max_workers=1) as pool:
        songs = _find_songs(searches, candidate_limit, skip_ids, Path(workdir), avoid_keys, blocked_keys)
        # fetch_songs downloads several clips ahead in parallel; this thread only hands them to the analyzer.
        pending = pool.submit(next, songs, None)
        try:
            while (found := pending.result()) is not None:
                song, song_query, tier = found
                # Start fetching the next song while this one is analyzed.
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
                yield {"type": "analyzing", "index": analyzed, "recommended_count": recommended, **result}

                # 5. Ask the audio model for a verdict; the clip is no longer needed after.
                verdict = analyze(song.clip_path, taste, exploration)
                song.clip_path.unlink(missing_ok=True)

                # 6. Cache the song so later runs skip it, then report.
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
