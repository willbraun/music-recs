# API

The Python API in [api.py](../api/api.py) is the only interface between the frontend and the backend. This is the reference for every endpoint: its input, its output, and its errors. Feature specs describe behavior and link here for shapes.

Status: each endpoint is marked **implemented** (in the code today), **changed** (it exists, and this spec changes it), or **planned** (new). Fields marked _planned_ do not exist yet.

## Conventions

- All routes are under `/api`, return JSON unless noted, and are local only (`127.0.0.1:8000`). There is no authentication.
- Timestamps are UTC text, `YYYY-MM-DD HH:MM:SS`.
- Errors are `{"detail": ...}`. `detail` is a readable string for errors the app raises itself (`404`, `409`, and the taste `422`). For malformed bodies and parameters, FastAPI's own validation returns `422` with `detail` as a list of objects. The client shows `detail` when it is a string and a generic message otherwise.

## Runs

A run finds and analyzes new songs. Runs are queued and processed one at a time, since there is one model on one device.

### `POST /api/runs`

Status: implemented. _Planned:_ the `409` below.

Starts a run and returns right away.

Request body:

| Field         | Type    | Default | Rules                        |
| ------------- | ------- | ------- | ---------------------------- |
| `query`       | string  | `null`  | Trimmed, 1 to 200 characters |
| `count`       | integer | `3`     | `1` to `50`                  |
| `exploration` | integer | `50`    | `0` to `100`                 |

Without a `query`, search queries are generated from the taste and the learned profile at the given `exploration` level.

Response `202`:

```json
{ "id": "3f6c0e5a9b7d4c1e8a2f5d6b7c8e9f01" }
```

`id` is an opaque string for the events endpoint. It is kept in memory only and is not the `runs.id` in the database.

Errors:

- `409` with `detail: "Set your taste first"` when no taste has been saved _(planned)_.
- `422` for invalid fields.

### `GET /api/runs/{run_id}/events`

Status: implemented.

A server-sent event stream of the run's progress. Content type `text/event-stream`.

- Optional request header `Last-Event-ID`: the stream resumes after that event index. Without it, the stream replays every event from the start, so a reload can reattach to a run.
- Each event is `id: <index>` and `data: <json>` followed by a blank line. The index starts at 0.
- A `: keepalive` comment is sent every 15 seconds while idle.
- The stream ends after the run finishes, which is after a `done` or `error` event.
- `404` with `detail: "Unknown run"` when the id is not known. Runs are forgotten when the server restarts.

Every event has a `type`. The shapes:

| `type`              | Fields                                                                                                                                      | Meaning                                           |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `started`           | `query` (string or null), `count`, `exploration`, `run_id` (integer, _planned_)                                                             | The taste is loaded and the run began             |
| `downloading_model` | `model` (string)                                                                                                                            | A model is not cached yet and is being downloaded |
| `queries`           | `queries`: list of `{query, tier}`                                                                                                          | Search queries were generated                     |
| `fetching`          | none                                                                                                                                        | Clips are being downloaded                        |
| `analyzing`         | `index`, `recommended_count`, `video_id`, `title`, `artist`, `url`, `query`, `tier`, `thumbnail_url` (_planned_)                            | The audio model is listening to a song            |
| `scored`            | `index`, `video_id`, `title`, `artist`, `url`, `query`, `tier`, `description`, `recommended` (boolean), plus the artwork fields (_planned_) | A verdict was reached and the song was saved      |
| `done`              | `analyzed`, `recommended`, `count`                                                                                                          | The run finished                                  |
| `error`             | `message` (string)                                                                                                                          | The run failed. This is the last event.           |

- `tier` is `familiar`, `adjacent`, or `adventurous` for generated queries, and `null` when the user gave a `query`.
- `description` is `Verdict: YES (N% confidence)` or `Verdict: NO (N% confidence)`.
- `started` currently also carries `taste_version`. It is removed along with `taste_versions` ([database.md](database.md#moving-an-existing-database-to-this-schema)); `run_id` replaces it.
- Analyses without a verdict produce no `scored` event.
- The artwork fields on `scored` are `thumbnail_url`, `album_art_url`, `album`, `musicbrainz_recording_id`, and `musicbrainz_release_group_id` ([artwork.md](artwork.md)).
- Home maps these events to its status text ([home.md](home.md#events)).

## Songs

### The `Song` object

Returned by `GET /api/songs`. A `scored` event carries the same fields except `analyzed_at` and `rating`.

| Field                          | Type               | Notes                                                           |
| ------------------------------ | ------------------ | --------------------------------------------------------------- |
| `video_id`                     | string             | YouTube video id                                                |
| `title`                        | string             |                                                                 |
| `artist`                       | string             |                                                                 |
| `url`                          | string             | `https://www.youtube.com/watch?v=<video_id>`                    |
| `description`                  | string             | `Verdict: YES (N% confidence)` or `Verdict: NO (N% confidence)` |
| `analyzed_at`                  | string             |                                                                 |
| `query`                        | string or null     | The search query that found the song. Null for old rows.        |
| `thumbnail_url`                | string             | _Planned._ [artwork.md](artwork.md)                             |
| `album_art_url`                | string or null     | _Planned._                                                      |
| `album`                        | string or null     | _Planned._                                                      |
| `musicbrainz_recording_id`     | string or null     | _Planned._                                                      |
| `musicbrainz_release_group_id` | string or null     | _Planned._                                                      |
| `recommended`                  | boolean            | Derived on read: the description starts with `Verdict: YES`     |
| `rating`                       | `1`, `-1`, or null | _Planned._ The user's rating. Null when unrated.                |

### `GET /api/songs`

Status: changed. Today it returns every song as a bare list, ordered newest first, with `taste_version` and no artwork. The paginated response below replaces it, and the legacy `web/` page that reads it must be updated or retired when it ships.

Query parameters:

| Parameter     | Type    | Default  | Description                                                                                      |
| ------------- | ------- | -------- | ------------------------------------------------------------------------------------------------ |
| `page`        | integer | `1`      | 1-based, `>= 1`                                                                                  |
| `page_size`   | integer | `24`     | `1` to `100`                                                                                     |
| `recommended` | boolean | omitted  | `true` returns only recommended songs, `false` only not recommended, omitted returns all         |
| `q`           | string  | omitted  | Case-insensitive substring match on `title`, `artist`, or `album`. Trimmed, 1 to 200 characters. |
| `sort`        | enum    | `newest` | `newest` is `analyzed_at DESC, rowid DESC`. `oldest` is `analyzed_at ASC, rowid ASC`.            |

Response `200`:

```json
{
	"items": [
		{
			"video_id": "abc123",
			"title": "Everything In Its Right Place",
			"artist": "Radiohead",
			"url": "https://www.youtube.com/watch?v=abc123",
			"description": "Verdict: YES (87% confidence)",
			"analyzed_at": "2026-10-10 14:03:22",
			"query": "experimental electronic rock",
			"thumbnail_url": "https://img.youtube.com/vi/abc123/hqdefault.jpg",
			"album_art_url": "https://coverartarchive.org/release-group/<mbid>/front-500",
			"album": "Kid A",
			"musicbrainz_recording_id": "<mbid>",
			"musicbrainz_release_group_id": "<mbid>",
			"recommended": true,
			"rating": 1
		}
	],
	"total": 128,
	"page": 1,
	"page_size": 24
}
```

- `total` is the number of songs matching the filters, ignoring paging.
- A page past the last returns `items: []` with the correct `total`.
- Invalid values return `422`.

How the page uses these is in [songs-page.md](songs-page.md).

### `PUT /api/songs/{video_id}/feedback`

Status: planned. See [learned-profile.md](learned-profile.md#rating-songs).

Saves the user's rating of a song, replacing any earlier one. Saving again resets the rating's timestamp.

Request body:

| Field    | Type    | Rules                        |
| -------- | ------- | ---------------------------- |
| `rating` | integer | `1` (like) or `-1` (dislike) |

Response `200`:

```json
{ "video_id": "abc123", "rating": -1, "created_at": "2026-10-10 14:10:00" }
```

Errors: `404` with `detail: "Unknown song"`, `422` for invalid fields.

### `DELETE /api/songs/{video_id}/feedback`

Status: planned.

Clears the song's rating. Response `204` with no body, including when the song had no rating. `404` with `detail: "Unknown song"` when the song does not exist.

## Taste

The user's taste. See [taste.md](taste.md).

### The `Taste` object

| Field        | Type   | Notes                                                              |
| ------------ | ------ | ------------------------------------------------------------------ |
| `profile`    | object | The fields the user entered, below                                 |
| `text`       | string | The text sent to the models, rendered from `profile` on every read |
| `updated_at` | string | When the taste was last saved                                      |

The `profile` object:

| Field              | Type            |
| ------------------ | --------------- |
| `liked_genres`     | list of strings |
| `liked_artists`    | list of strings |
| `disliked_genres`  | list of strings |
| `disliked_artists` | list of strings |
| `notes`            | string          |

```json
{
	"profile": {
		"liked_genres": ["Electronic", "Indie rock"],
		"liked_artists": ["Tame Impala", "Flume"],
		"disliked_genres": ["Country"],
		"disliked_artists": [],
		"notes": "If songs have lyrics, they should be in English."
	},
	"text": "I like these genres: Electronic, Indie rock. My favorite artists are Tame Impala, Flume. Never recommend these genres: Country. Notes: If songs have lyrics, they should be in English.",
	"updated_at": "2026-10-10 12:00:00"
}
```

### `GET /api/taste`

Status: planned.

Returns the `Taste`, or `null` when none has been saved. `200` in both cases.

### `PUT /api/taste`

Status: planned.

Request body: `{ "profile": { ... } }`. The server normalizes the fields, validates them against the [taste rules](taste.md#rules), and overwrites the saved taste.

Response `200`: the saved `Taste`, with the normalized `profile`.

Errors: `422` with `detail` as one readable message, the first rule that failed. Nothing is saved on error.

Saving while a run is active is allowed. A run reads the taste once when it starts.

## Static files

`GET /` and every path not under `/api` serve the frontend build, with `index.html` as the fallback for client-side routes ([frontend.md](frontend.md#serving)). They are mounted after the API routes so they never shadow them.
