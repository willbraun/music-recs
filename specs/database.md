# Database

The app uses one SQLite file, `api/app.db`, accessed through `AppDb` in [appdb.py](../api/appdb.py). It is opened through [db.py](../api/db.py), which uses a new connection per operation, returns rows as `sqlite3.Row`, and turns on `PRAGMA foreign_keys` for every connection. All timestamps are UTC text from `CURRENT_TIMESTAMP` (`YYYY-MM-DD HH:MM:SS`). Nothing in it can be rebuilt, so do not delete it.

## Migrations

The schema is versioned by numbered SQL files in [api/migrations/](../api/migrations/), applied by [migrate.py](../api/migrate.py) when `AppDb` is constructed.

- Files are named `NNNN_name.sql`, numbered from `0001` with no gaps. The file number is the schema version, stored in `PRAGMA user_version`.
- On startup each file newer than the stored version runs in one transaction together with the version bump, so a failed migration leaves the database at the previous version. Files must not contain `BEGIN` or `COMMIT`.
- A database whose version is newer than the newest file is rejected.
- To change the schema, add the next numbered file. Never edit one that has been applied.
- SQLite cannot alter a constraint in place, so changing one means creating a new table, copying rows, dropping the old table, and renaming.
- The database uses WAL mode, so `app.db-wal` and `app.db-shm` appear next to it.

`0001_initial.sql` creates all three tables below.

## `songs`

One row per analyzed song. Songs are permanent, since `feedback` refers to them.

| Column          | Type    | Constraints                         | Description                                                                                                                          |
| --------------- | ------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `video_id`      | TEXT    | PRIMARY KEY                         | YouTube video id                                                                                                                     |
| `title`         | TEXT    | NOT NULL                            | Song title                                                                                                                           |
| `artist`        | TEXT    | NOT NULL                            | Artist name                                                                                                                          |
| `url`           | TEXT    | NOT NULL                            | `https://www.youtube.com/watch?v=<video_id>`                                                                                         |
| `description`   | TEXT    | NOT NULL                            | Music Flamingo's verdict for the clip, `Verdict: YES (N% confidence)` or `Verdict: NO (N% confidence)`, from the YES/NO token logits |
| `analyzed_at`   | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the song was analyzed                                                                                                           |
| `taste_version` | INTEGER | REFERENCES `taste_versions(id)`     | The taste version the song was analyzed under. NULL for rows from before this column existed.                                        |
| `query`         | TEXT    |                                     | Search query that found the song. NULL for rows from before this column existed.                                                     |

- `AppDb.add_song` is an upsert, so re-adding a `video_id` overwrites the row and resets `analyzed_at`. It does not use `INSERT OR REPLACE`, which deletes the row first and would fail on a rated song.
- `AppDb.list_songs` filters, orders (default `analyzed_at DESC, rowid DESC`), and pages in SQL. See [songs-page.md](songs-page.md#api).
- How the display columns are filled is described in [artwork.md](artwork.md).
- Songs whose analysis has no verdict are not stored. A song counts as recommended when its description starts with `Verdict: YES`; this is derived on read, not stored.

`thumbnail_url`, `album_art_url`, `album`, `musicbrainz_recording_id`, and `musicbrainz_release_group_id` are planned in [artwork.md](artwork.md) and are not in `0001`. They arrive in a later migration, which also runs `UPDATE songs SET thumbnail_url = 'https://img.youtube.com/vi/' || video_id || '/hqdefault.jpg'` so every existing row has a thumbnail.

## `taste_versions`

Append-only history of the taste text. The current taste is the row with the highest `id`, so there is no "current" flag.

| Column       | Type    | Constraints                         | Description                                                        |
| ------------ | ------- | ----------------------------------- | ------------------------------------------------------------------ |
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT           | Version number, stored on `songs.taste_version`                    |
| `text`       | TEXT    | NOT NULL                            | Full taste text, inserted into the Music Flamingo prompt unchanged |
| `source`     | TEXT    | NOT NULL                            | How the version was created. Only `seed` is written so far.        |
| `note`       | TEXT    |                                     | Why the version was created. Not written yet.                      |
| `created_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the version was created                                       |

- If the table is empty on startup, version 1 is inserted with `source = 'seed'` and the text of `SEED_TASTE` in [appdb.py](../api/appdb.py). `SEED_TASTE` is not read again after that.
- SQLite also creates an internal `sqlite_sequence` table for the `AUTOINCREMENT` counter. The app does not use it directly.

## `feedback`

One rating per song. Nothing writes to this table yet. The taste version a song was rated under is `songs.taste_version`.

| Column       | Type    | Constraints                                                  | Description                              |
| ------------ | ------- | ------------------------------------------------------------ | ---------------------------------------- |
| `video_id`   | TEXT    | PRIMARY KEY, REFERENCES `songs(video_id)` ON DELETE RESTRICT | The rated song                           |
| `rating`     | INTEGER | NOT NULL, CHECK (`rating` IN (-1, 1))                        | `1` is a like, `-1` is a dislike         |
| `note`       | TEXT    |                                                              | Optional free-text reason for the rating |
| `created_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | When the rating was saved                |

## Relationships

- `songs.taste_version` refers to `taste_versions.id`, and `feedback.video_id` refers to `songs.video_id`. Both are enforced.
- Because every rated song has a `songs` row, searches skip `songs.video_id` alone (`AppDb.get_seen_ids`).
