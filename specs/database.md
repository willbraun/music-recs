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

The original schema had a `taste_versions` table, `songs.taste_version`, and `songs.description` (a Music Flamingo verdict). They are replaced by the single-row `taste` table, `songs.score`, `songs.recommended`, and `song_embeddings`, in new migrations. An applied migration is never edited, so an existing `app.db` runs the new ones.

- `taste_versions` is dropped with its history, including the seed taste, so the user enters their taste again. Songs are kept.
- `songs.taste_version` and `songs.description` are removed. `recommended` is set from the old description (`Verdict: YES` becomes 1), and `score` stays NULL for existing songs, since the old confidence is not comparable to the new score.
- SQLite cannot drop a column that is a foreign key, and `feedback`'s `ON DELETE RESTRICT` blocks dropping a referenced table that has rows. So the migration sets the `feedback` rows aside, drops `feedback`, rebuilds `songs` without the columns, recreates `feedback` without its unused `note` column, and restores the ratings.
- Existing rated songs get embeddings from the backfill command in [scoring.md](scoring.md#existing-songs).

## `songs`

One row per analyzed song. Songs are permanent, since `feedback` refers to them.

| Column        | Type    | Constraints                               | Description                                                                                                     |
| ------------- | ------- | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `video_id`    | TEXT    | PRIMARY KEY                               | YouTube video id                                                                                                |
| `title`       | TEXT    | NOT NULL                                  | Song title                                                                                                      |
| `artist`      | TEXT    | NOT NULL                                  | Artist name                                                                                                     |
| `url`         | TEXT    | NOT NULL                                  | `https://www.youtube.com/watch?v=<video_id>`                                                                    |
| `score`       | REAL    |                                           | Match score from 0 to 1 ([scoring.md](scoring.md#score)). NULL for songs analyzed before scoring existed.       |
| `recommended` | INTEGER | NOT NULL, CHECK (`recommended` IN (0, 1)) | `1` when `score` met the run's threshold. Stored, because the threshold depends on the run's exploration level. |
| `analyzed_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP       | When the song was analyzed                                                                                      |
| `query`       | TEXT    |                                           | Search query that found the song. NULL for rows from before this column existed.                                |

- `AppDb.add_song` is an upsert, so re-adding a `video_id` overwrites the row and resets `analyzed_at`. It does not use `INSERT OR REPLACE`, which deletes the row first and would fail on a rated song. It also writes the song's `song_embeddings` row in the same transaction.
- `AppDb.list_songs` filters, orders (default `analyzed_at DESC, rowid DESC`), and pages in SQL. See [songs-page.md](songs-page.md#api).
- How the display columns are filled is described in [artwork.md](artwork.md).
- Every analyzed song is stored, recommended or not.

`thumbnail_url`, `album_art_url`, `album`, `musicbrainz_recording_id`, and `musicbrainz_release_group_id` are planned in [artwork.md](artwork.md) and are not in the schema yet. They arrive in a later migration, which also runs `UPDATE songs SET thumbnail_url = 'https://img.youtube.com/vi/' || video_id || '/hqdefault.jpg'` so every existing row has a thumbnail.

## `taste`

The user's current taste, in one row. `id` is always `1` and the row is overwritten on every save. There is no version history.

| Column       | Type    | Constraints                         | Description                                                                                                          |
| ------------ | ------- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `id`         | INTEGER | PRIMARY KEY, CHECK (`id` = 1)       | Fixed, so the table cannot hold a second row                                                                         |
| `profile`    | TEXT    | NOT NULL                            | JSON of the fields the user entered, `{liked_genres, liked_artists, disliked_genres}` ([taste.md](taste.md#storage)) |
| `updated_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | When the taste was last saved                                                                                        |

- The text for query generation is rendered from `profile` when a run starts and is never stored.
- The table is empty on a fresh database and after the upgrade above. The user must save a taste before runs are allowed ([taste.md](taste.md#first-run)). `AppDb.get_current_taste` returns `None` until then.
- Saving is an upsert (`INSERT ... ON CONFLICT (id) DO UPDATE`).

## `song_embeddings`

One audio embedding per analyzed song, written with the song by `AppDb.add_song`. See [scoring.md](scoring.md#embeddings).

| Column       | Type | Constraints                               | Description                                                               |
| ------------ | ---- | ----------------------------------------- | ------------------------------------------------------------------------- |
| `video_id`   | TEXT | PRIMARY KEY, REFERENCES `songs(video_id)` | The embedded song                                                         |
| `model`      | TEXT | NOT NULL                                  | Hugging Face id of the embedding model, `OpenMuQ/MuQ-MuLan-large`         |
| `embedding`  | BLOB | NOT NULL                                  | Little-endian float32 values, L2-normalized, read with `numpy.frombuffer` |
| `created_at` | TEXT | NOT NULL, DEFAULT CURRENT_TIMESTAMP       | When the embedding was computed                                           |

- The scorer ignores rows whose `model` is not the current one.
- Nothing else needs an index or a vector extension. All embeddings are loaded into memory when needed.

## `feedback`

One rating per song. Written by the rating endpoints planned in [scoring.md](scoring.md#rating-songs); nothing writes to it yet.

| Column       | Type    | Constraints                                                  | Description                                                                               |
| ------------ | ------- | ------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| `video_id`   | TEXT    | PRIMARY KEY, REFERENCES `songs(video_id)` ON DELETE RESTRICT | The rated song                                                                            |
| `rating`     | INTEGER | NOT NULL, CHECK (`rating` IN (-1, 1))                        | `1` is a like, `-1` is a dislike                                                          |
| `created_at` | TEXT    | NOT NULL, DEFAULT CURRENT_TIMESTAMP                          | When the rating was saved. Re-rating resets it. Used to find the most recent liked songs. |

## Relationships

- `feedback.video_id` and `song_embeddings.video_id` refer to `songs.video_id`. Both are enforced. `taste` is independent of the other tables.
- Because every rated song has a `songs` row, searches skip `songs.video_id` alone (`AppDb.get_seen_ids`).
