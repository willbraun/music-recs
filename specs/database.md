# Database

The app uses one SQLite file, `api/app.db`, accessed through `AppDb` in [appdb.py](../api/appdb.py). It is opened through [db.py](../api/db.py), which uses a new connection per operation, returns rows as `sqlite3.Row`, and turns on `PRAGMA foreign_keys` for every connection. All timestamps are UTC text from `CURRENT_TIMESTAMP` (`YYYY-MM-DD HH:MM:SS`). Nothing in it can be rebuilt, so do not delete it.

## Migrations

The schema is versioned by numbered SQL files in [api/migrations/](../api/migrations/), applied by [migrate.py](../api/migrate.py) when `AppDb` is constructed.

- Files are named `NNNN_name.sql`, numbered in order with no gaps. The file number is the schema version, stored in `PRAGMA user_version`.
- On startup each file newer than the stored version runs in one transaction together with the version bump, so a failed migration leaves the database at the previous version. Files must not contain `BEGIN` or `COMMIT`.
- A database whose version is newer than the newest file is rejected.
- To change the schema, add the next numbered file. Never edit one that has been applied.
- SQLite cannot alter a constraint in place, so changing one means creating a new table, copying rows, dropping the old table, and renaming.
- The database uses WAL mode, so `app.db-wal` and `app.db-shm` appear next to it.

## Moving an existing database to this schema

The original schema had a `taste_versions` table and `songs.taste_version`. They are replaced by the single-row `taste` table and `runs`, in a new migration. An applied migration is never edited, so an existing `app.db` runs the new one.

- `taste_versions` is dropped with its history, including the seed taste, so the user enters their taste again. Songs are kept.
- `songs.taste_version` is removed and `songs.run_id` is added.
- SQLite cannot drop a column that is a foreign key, and `feedback`'s `ON DELETE RESTRICT` blocks dropping a referenced table that has rows. So the migration sets the `feedback` rows aside, drops `feedback`, rebuilds `songs` without the column, recreates `feedback` without its unused `note` column, and restores the ratings.

## `songs`

One row per analyzed song. Songs are permanent, since `feedback` refers to them.

| Column        | Type    | Constraints                         | Description                                                                                                                           |
| ------------- | ------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `video_id`    | TEXT    | PRIMARY KEY                         | YouTube video id                                                                                                                      |
| `title`       | TEXT    | NOT NULL                            | Song title                                                                                                                            |
| `artist`      | TEXT    | NOT NULL                            | Artist name                                                                                                                           |
| `url`         | TEXT    | NOT NULL                            | `https://www.youtube.com/watch?v=<video_id>`                                                                                          |
| `description` | TEXT    | NOT NULL                            | Music Flamingo's verdict for the clip, `Verdict: YES (N% confidence)` or `Verdict: NO (N% confidence)`, from the YES/NO token logits  |
| `analyzed_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the song was analyzed                                                                                                            |
| `query`       | TEXT    |                                     | Search query that found the song. NULL for rows from before this column existed.                                                      |
| `run_id`      | INTEGER | REFERENCES `runs(id)`               | The run that analyzed the song, which holds the taste and learned profile it used. NULL for songs analyzed before runs were recorded. |

- `AppDb.add_song` is an upsert, so re-adding a `video_id` overwrites the row and resets `analyzed_at`. It does not use `INSERT OR REPLACE`, which deletes the row first and would fail on a rated song.
- `AppDb.list_songs` filters, orders (default `analyzed_at DESC, rowid DESC`), and pages in SQL. See [songs-page.md](songs-page.md#api).
- How the display columns are filled is described in [artwork.md](artwork.md).
- Songs whose analysis has no verdict are not stored. A song counts as recommended when its description starts with `Verdict: YES`; this is derived on read, not stored.

`thumbnail_url`, `album_art_url`, `album`, `musicbrainz_recording_id`, and `musicbrainz_release_group_id` are planned in [artwork.md](artwork.md) and are not in the schema yet. They arrive in a later migration, which also runs `UPDATE songs SET thumbnail_url = 'https://img.youtube.com/vi/' || video_id || '/hqdefault.jpg'` so every existing row has a thumbnail.

## `taste`

The user's current taste, in one row. `id` is always `1` and the row is overwritten on every save. There is no version history. What a run used is saved on `runs`.

| Column       | Type    | Constraints                         | Description                                                                                                                                   |
| ------------ | ------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`         | INTEGER | PRIMARY KEY, CHECK (`id` = 1)       | Fixed, so the table cannot hold a second row                                                                                                  |
| `profile`    | TEXT    | NOT NULL                            | JSON of the fields the user entered, `{liked_genres, liked_artists, disliked_genres, disliked_artists, notes}` ([taste.md](taste.md#storage)) |
| `updated_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the taste was last saved                                                                                                                 |

- The text sent to the models is rendered from `profile` when a run starts and is never stored here, so it cannot drift from the fields.
- The table is empty on a fresh database and after the upgrade above. The user must save a taste before runs are allowed ([taste.md](taste.md#first-run)). `AppDb.get_current_taste` returns `None` until then.
- Saving is an upsert (`INSERT ... ON CONFLICT (id) DO UPDATE`).

## `runs`

One row per run. It saves the inputs the run actually sent to the models, so "what produced this song" is a lookup through `songs.run_id`, not a guess from dates or from the current taste. Written by `AppDb.add_run` at the start of a run. See [learned-profile.md](learned-profile.md#run-snapshot).

| Column            | Type    | Constraints                         | Description                                                                                                |
| ----------------- | ------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `id`              | INTEGER | PRIMARY KEY AUTOINCREMENT           | Stored on `songs.run_id`. Separate from the in-memory run id the API hands to clients.                     |
| `started_at`      | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the run started                                                                                       |
| `query`           | TEXT    |                                     | The requested search query, or NULL when queries were generated                                            |
| `count`           | INTEGER | NOT NULL                            | Songs requested                                                                                            |
| `exploration`     | INTEGER | NOT NULL                            | Exploration level, 0-100                                                                                   |
| `taste_text`      | TEXT    | NOT NULL                            | The taste text rendered from `taste.profile` and sent to the models                                        |
| `learned_profile` | TEXT    |                                     | The learned profile text rendered on the fly from feedback and sent to the models. NULL when it was empty. |

## `feedback`

One rating per song. Written by the rating endpoints planned in [learned-profile.md](learned-profile.md#rating-songs); nothing writes to it yet.

| Column       | Type    | Constraints                                                  | Description                                                                         |
| ------------ | ------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| `video_id`   | TEXT    | PRIMARY KEY, REFERENCES `songs(video_id)` ON DELETE RESTRICT | The rated song                                                                      |
| `rating`     | INTEGER | NOT NULL, CHECK (`rating` IN (-1, 1))                        | `1` is a like, `-1` is a dislike                                                    |
| `created_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | When the rating was saved. Re-rating resets it. Used to break ties between artists. |

## Relationships

- `songs.run_id` refers to `runs.id`, and `feedback.video_id` refers to `songs.video_id`. Both are enforced. `taste` and `runs` are otherwise independent, since a run stores a copy of the taste it used.
- Because every rated song has a `songs` row, searches skip `songs.video_id` alone (`AppDb.get_seen_ids`).
