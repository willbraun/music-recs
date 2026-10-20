# Artwork and song metadata

Each analyzed song is enriched with display metadata: an album art image, the album name, and MusicBrainz ids. This is done by the backend, so the frontend never calls MusicBrainz or the Cover Art Archive directly ([frontend.md](frontend.md#api-client)). The results are stored in `app.db` ([database.md](database.md)) so they are looked up once.

## Why the backend

- MusicBrainz requires a descriptive `User-Agent` header and allows about 1 request per second. One place can enforce that; many browser tabs cannot.
- Lookups can be stored with the song, so the Songs page needs no extra requests.

## New data

Added to `songs` in `app.db` by a new numbered migration in `api/migrations/`. All are nullable.

| Column                         | Source                          | Notes                                                        |
| ------------------------------ | ------------------------------- | ------------------------------------------------------------ |
| `thumbnail_url`                | YouTube                         | `https://img.youtube.com/vi/{video_id}/hqdefault.jpg`        |
| `album_art_url`                | Cover Art Archive               | `https://coverartarchive.org/release-group/{rgid}/front-500` |
| `album`                        | MusicBrainz release group title | Display only                                                 |
| `musicbrainz_recording_id`     | MusicBrainz recording search    | Which recording was matched                                  |
| `musicbrainz_release_group_id` | MusicBrainz recording search    | Used to build the artwork URL                                |

`thumbnail_url` is deterministic from the video id, so it is always set. The four MusicBrainz-derived columns are NULL when there is no confident match.

## Lookup procedure

Runs in the backend for each song, after the clip is fetched and before the audio verdict ([pipeline.py](../api/pipeline.py)), so the loading card can show the same art as the final card. Every analyzed song is looked up, whether or not it ends up recommended.

### 1. Find the recording

```
GET https://musicbrainz.org/ws/2/recording/?query=artist:"Radiohead" AND recording:"Everything In Its Right Place" AND status:official&fmt=json&limit=25
```

- Use the song's `artist` and `title`. Escape Lucene special characters and double quotes in both values.
- `status:official` keeps bootleg live recordings from crowding out the studio release in the results.
- Consider every result that meets all of:
  - `score >= 90`.
  - Its title equals the song title after normalizing case, punctuation, and surrounding whitespace.
  - It has at least one release with a release group.
- For each, choose the release group in this order: primary type Album, then EP, then Single. Skip release groups with a secondary type of Compilation, Live, Soundtrack, or Remix unless nothing else is available.
- Of those candidates, use the one with the best release group by the same order. Ties go to the earlier search result.
- Store the recording `id`, the chosen release group `id`, and the release group `title` as `album`.
- No result that meets the rules means no match. Store NULLs for the four columns.

### 2. Check the artwork

```
HEAD https://coverartarchive.org/release-group/{rgid}/front-500
```

Documentation: https://musicbrainz.org/doc/Cover_Art_Archive/API

- Size `500` is used everywhere. The API also supports `250` and `1200` if cards or views change later.
- The URL redirects to the image. Follow redirects and treat a final 2xx as success. A 404 means the release group has no front cover.
- On success, store the URL (without the redirect target) in `album_art_url`.
- On 404, leave `album_art_url` NULL but still store `album` and the MusicBrainz ids.

### Request rules

- `User-Agent: music-recs/<version> (<contact>)`. The contact value is a constant in the code that the user must set. It is not read from user input.
- At most 1 MusicBrainz request per second, enforced by a shared rate limiter in the lookup module. Cover Art Archive requests are not limited this way, but run sequentially.
- Timeout of 5 seconds per request.
- Any network error, timeout, or 5xx is treated as no match for that song. A 503 (MusicBrainz is busy) is retried up to 3 attempts in total, each spaced by the rate limiter, before giving up. The failure is logged. It never fails the run and never blocks the song from being cached or sent.

## Pipeline changes

- The `analyzing` event gains `thumbnail_url` and `album_art_url` so the loading card can show the real art ([home.md](home.md#recommendations-grid)).
- The `scored` event gains `thumbnail_url`, `album_art_url`, `album`, `musicbrainz_recording_id`, and `musicbrainz_release_group_id`.
- `AppDb.add_song` takes the five new values and stores them. `AppDb.list_songs` returns them.
- Lookups run on the pipeline's consumer thread, before the `analyzing` event. Clips are already prefetched in parallel, so the added delay (about 1 to 2 seconds per song) overlaps with other work.

## Frontend fallback

The frontend picks an image in this order: `album_art_url`, then `thumbnail_url`, then a placeholder. A failed image load moves to the next one. See [song-card.md](song-card.md#artwork).

## Existing rows

- The migration fills `thumbnail_url` for every existing row from its `video_id`. See [database.md](database.md#migrations).
- Existing rows keep NULL for the four MusicBrainz-derived columns, and the cards use the YouTube thumbnail. A one-time backfill command that looks up songs with NULL `musicbrainz_recording_id` may be added later. Because "not looked up" and "no match" are both NULL, such a backfill would retry songs that had no match.

## Testing

- Unit tests cover query escaping, title normalization, match selection (score threshold, release group preference), and URL building, using recorded sample MusicBrainz responses. No test calls the real network.
- Tests cover the failure paths: timeout, 503, no match, and a 404 from the Cover Art Archive.
