import math
import re
import tempfile
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterator

import numpy as np
from appdb import AppDb
from fetch import OVERFETCH, Song, fetch_songs, is_artist_match

MAX_QUERIES = 6
CANDIDATES_PER_RECOMMENDATION = 2
MAX_SEARCH_RESULTS_PER_QUERY = 300
SEED_SONGS_PER_ARTIST = 3


def _find_songs(
    searches: list[tuple[str, str | None]],
    count: int,
    skip_ids: set[str],
    workdir: Path,
    disliked_artists: Collection[str] = (),
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
            for song in fetch_songs(query, share, skip_ids, workdir, disliked_artists):
                # Later queries and batches must not return this song again.
                skip_ids.add(song.video_id)
                remaining -= 1
                yield song, query, tier
        if count == max_count:
            return
        count = min(count * 2, max_count)


def _download_model_if_missing(model_id: str) -> Iterator[dict]:
    """Yield a downloading_model event and download the model, unless it is already cached."""
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import LocalEntryNotFoundError

    try:
        snapshot_download(model_id, local_files_only=True)
    except LocalEntryNotFoundError:
        yield {"type": "downloading_model", "model": model_id}
        snapshot_download(model_id)


def _get_primary_artist(song_artist: str) -> str:
    return re.split(r"\s*[,/&]\s*", song_artist.casefold())[0]


def _seed_liked_artists(
    artists: Collection[str],
    stored: list[tuple[str, np.ndarray]],
    skip_ids: set[str],
    workdir: Path,
    embed_audio: Callable[[Path], np.ndarray],
) -> Iterator[dict]:
    """Embed songs by liked artists that have fewer than SEED_SONGS_PER_ARTIST analyzed songs.

    Yields a seeding event per artist and returns the (song, embedding) pairs, which the caller stores.
    """
    seeds: list[tuple[Song, np.ndarray]] = []
    for artist in artists:
        needed = SEED_SONGS_PER_ARTIST - sum(is_artist_match(song_artist, artist) for song_artist, _ in stored)
        if needed <= 0:
            continue
        yield {"type": "seeding", "artist": artist}
        for song in fetch_songs(artist, needed, skip_ids, workdir, required_artist=artist):
            embedding = embed_audio(song.clip_path)
            song.clip_path.unlink(missing_ok=True)
            seeds.append((song, embedding))
    return seeds


def run(    query: str | None,
    count: int,
    exploration: int,
    appdb: AppDb,
) -> Iterator[dict]:
    """Find and score new songs, yielding a progress event dict per step.

    Without a `query`, search queries are generated from the taste at the given `exploration` level (0-100).
    """
    # Heavy imports are deferred so --help and server startup stay fast.
    from embed import MODEL_ID as EMBEDDING_MODEL_ID
    from embed import embed_audio
    from queries import MODEL_ID as QUERY_MODEL_ID
    from queries import RECENT_LIKES, generate_queries
    from scorer import build_scorer, get_threshold
    from taste_profile import render_taste

    # 1. Load the current taste and the ids that must not be recommended again.
    taste = appdb.get_current_taste()
    if taste is None:
        raise ValueError("Set your taste first")
    profile = taste.profile
    skip_ids = appdb.get_seen_ids()
    yield {"type": "started", "query": query, "count": count, "exploration": exploration}

    # 2. Use the given query, or generate queries from the taste at this exploration level.
    candidate_limit = count * CANDIDATES_PER_RECOMMENDATION
    if query is None:
        yield from _download_model_if_missing(QUERY_MODEL_ID)
        generated = generate_queries(
            render_taste(profile),
            exploration,
            min(candidate_limit, MAX_QUERIES),
            profile.liked_artists,
            appdb.get_recent_likes(RECENT_LIKES),
        )
        searches = [(g.query, g.tier) for g in generated]
        yield {"type": "queries", "queries": [{"query": q, "tier": tier} for q, tier in searches]}
    else:
        searches = [(query, None)]

    # 3. Seed songs by liked artists, then build the scorer from the taste, the ratings, and those songs.
    yield from _download_model_if_missing(EMBEDDING_MODEL_ID)
    threshold = get_threshold(exploration)
    stored = appdb.get_artist_embeddings(EMBEDDING_MODEL_ID)
    analyzed = 0
    recommended = 0
    recommended_artists: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="music-recs-") as workdir, ThreadPoolExecutor(max_workers=1) as pool:
        seeds = yield from _seed_liked_artists(profile.liked_artists, stored, skip_ids, Path(workdir), embed_audio)
        artist_embeddings = [
            embedding
            for song_artist, embedding in stored
            if any(is_artist_match(song_artist, artist) for artist in profile.liked_artists)
        ] + [embedding for _, embedding in seeds]
        scorer = build_scorer(profile, appdb.get_rated_embeddings(EMBEDDING_MODEL_ID), artist_embeddings)
        # Seed songs are stored like any analyzed song, so they show on the Songs page and are not fetched again.
        for song, embedding in seeds:
            score = scorer.score(embedding)
            appdb.add_song(
                song.video_id,
                song.title,
                song.artist,
                song.url,
                score,
                score >= threshold,
                song.artist,
                embedding,
                EMBEDDING_MODEL_ID,
            )
        yield {"type": "fetching"}
        songs = _find_songs(searches, candidate_limit, skip_ids, Path(workdir), profile.disliked_artists)
        # fetch_songs downloads several clips ahead in parallel; this thread only hands them to the embedder.
        pending = pool.submit(next, songs, None)
        try:
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

                # 4. Embed the clip and score it. The embedding is the only trace of the audio that is kept.
                embedding = embed_audio(song.clip_path)
                song.clip_path.unlink(missing_ok=True)
                score = scorer.score(embedding)
                # One recommendation per artist in a run, so a favorite artist cannot fill the whole batch.
                artist_key = _get_primary_artist(song.artist)
                is_recommended = score >= threshold and artist_key not in recommended_artists
                if is_recommended:
                    recommended_artists.add(artist_key)

                # 5. Store every song so later runs skip it, then report the result.
                appdb.add_song(
                    song.video_id,
                    song.title,
                    song.artist,
                    song.url,
                    score,
                    is_recommended,
                    song_query,
                    embedding,
                    EMBEDDING_MODEL_ID,
                )

                recommended += is_recommended
                yield {
                    "type": "scored",
                    "index": analyzed,
                    **result,
                    "score": score,
                    "recommended": is_recommended,
                }
                if recommended >= count:
                    break
        finally:
            # Let the in-flight pull finish, then stop downloads before the workdir is deleted.
            pool.shutdown(wait=True)
            songs.close()

    yield {"type": "done", "analyzed": analyzed, "recommended": recommended, "count": count}
