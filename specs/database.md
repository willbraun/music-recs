# Database

The app uses two SQLite files in the project root. Both are opened through [db.py](../db.py), which uses a new connection per operation and returns rows as `sqlite3.Row`. All timestamps are UTC text from `CURRENT_TIMESTAMP` (`YYYY-MM-DD HH:MM:SS`).

| File       | Module                  | Purpose                                                  | Safe to delete |
| ---------- | ----------------------- | -------------------------------------------------------- | -------------- |
| `cache.db` | [cache.py](../cache.py) | Analyzed songs, so they are not analyzed again           | Yes            |
| `app.db`   | [appdb.py](../appdb.py) | Taste history and song feedback, which cannot be rebuilt | No             |

Tables are created with `CREATE TABLE IF NOT EXISTS` when `Cache` or `AppDb` is constructed.

## cache.db

### `songs`

One row per analyzed song.

| Column          | Type    | Constraints                         | Description                                                                                                                                                               |
| --------------- | ------- | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `video_id`      | TEXT    | PRIMARY KEY                         | YouTube video id                                                                                                                                                          |
| `title`         | TEXT    | NOT NULL                            | Song title                                                                                                                                                                |
| `artist`        | TEXT    | NOT NULL                            | Artist name                                                                                                                                                               |
| `url`           | TEXT    | NOT NULL                            | `https://www.youtube.com/watch?v=<video_id>`                                                                                                                              |
| `description`   | TEXT    | NOT NULL                            | Music Flamingo's description for the clip, starting with `Verdict: YES` or `Verdict: NO`                                                                                  |
| `analyzed_at`   | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the song was analyzed                                                                                                                                                |
| `taste_version` | INTEGER |                                     | `taste_versions.id` in `app.db` that the song was analyzed under. NULL for rows from before this column existed. No foreign key, since the tables are in different files. |
| `query`         | TEXT    |                                     | Search query that found the song. NULL for rows from before this column existed.                                                                                          |

- `Cache.add` uses `INSERT OR REPLACE`, so re-adding a `video_id` overwrites the row.
- `Cache.list_songs` orders by `analyzed_at DESC, rowid DESC`.
- Songs whose analysis has no verdict are not stored. A song counts as recommended when its description starts with `Verdict: YES`; this is derived on read, not stored.

### Migration

`taste_version` and `query` were added after the first release. On startup `Cache` reads `PRAGMA table_info(songs)` and runs `ALTER TABLE songs ADD COLUMN` for any that are missing. This is why an upgraded database lists them last, after `analyzed_at`. Existing rows keep NULL in both. The `score` column from earlier versions is removed with `ALTER TABLE songs DROP COLUMN score` if present.

## app.db

### `taste_versions`

Append-only history of the taste text. The current taste is the row with the highest `id`, so there is no "current" flag.

| Column       | Type    | Constraints                         | Description                                                                  |
| ------------ | ------- | ----------------------------------- | ---------------------------------------------------------------------------- |
| `id`         | INTEGER | PRIMARY KEY AUTOINCREMENT           | Version number, stored on `songs.taste_version` and `feedback.taste_version` |
| `text`       | TEXT    | NOT NULL                            | Full taste text, inserted into the Music Flamingo prompt unchanged           |
| `source`     | TEXT    | NOT NULL                            | How the version was created. Only `seed` is written so far.                  |
| `note`       | TEXT    |                                     | Why the version was created. Not written yet.                                |
| `created_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the version was created                                                 |

- If the table is empty on startup, version 1 is inserted with `source = 'seed'` and the text of `SEED_TASTE` in [appdb.py](../appdb.py). `SEED_TASTE` is not read again after that.
- SQLite also creates an internal `sqlite_sequence` table for the `AUTOINCREMENT` counter. The app does not use it directly.

### `feedback`

One rating per song. Song details are copied from `songs`, so a row stays useful after `cache.db` is deleted. Nothing writes to this table yet; `AppDb.get_rated_ids` reads it so rated songs are skipped in searches.

| Column          | Type    | Constraints                         | Description                                      |
| --------------- | ------- | ----------------------------------- | ------------------------------------------------ |
| `video_id`      | TEXT    | PRIMARY KEY                         | YouTube video id                                 |
| `title`         | TEXT    | NOT NULL                            | Copy of the song title                           |
| `artist`        | TEXT    | NOT NULL                            | Copy of the artist name                          |
| `url`           | TEXT    | NOT NULL                            | Copy of the song URL                             |
| `description`   | TEXT    | NOT NULL                            | Copy of the Music Flamingo description           |
| `taste_version` | INTEGER |                                     | `taste_versions.id` the song was analyzed under  |
| `rating`        | INTEGER | NOT NULL                            | The user's rating. The scale is not decided yet. |
| `note`          | TEXT    |                                     | Optional free-text reason for the rating         |
| `created_at`    | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the rating was saved                        |

## Relationships across files

- `songs.taste_version` and `feedback.taste_version` refer to `taste_versions.id`. SQLite cannot enforce this across files, so nothing checks it.
- Searches skip the union of `songs.video_id` (from `cache.db`) and `feedback.video_id` (from `app.db`), so rated songs stay skipped after `cache.db` is deleted.
