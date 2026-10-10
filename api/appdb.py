from pathlib import Path

from db import connect
from migrate import apply_migrations

DB_PATH = Path(__file__).parent / "app.db"

SEED_TASTE = "Electronic, dance, 2010's indie rock/pop, synthpop, grunge, hip hop, rock, blues, bluegrass, melodic metal. No country, world, Christian, or children's music. My favorite artists are Tame Impala, Cherub, New Order, Opeth, BORNS, GROUPLOVE, The Black Keys, Glass Animals, Todd Terge, Mac Miller, Flume. If songs have lyrics, they should be in English."


class AppDb:
    """Songs, taste history, and song feedback. Schema changes go in api/migrations."""

    def __init__(self, path: Path = DB_PATH):
        self._path = path
        with connect(path) as conn:
            apply_migrations(conn)
            if conn.execute("SELECT 1 FROM taste_versions").fetchone() is None:
                conn.execute("INSERT INTO taste_versions (text, source) VALUES (?, 'seed')", (SEED_TASTE,))

    def get_current_taste(self) -> tuple[int, str]:
        with connect(self._path) as conn:
            row = conn.execute("SELECT id, text FROM taste_versions ORDER BY id DESC LIMIT 1").fetchone()
            return row["id"], row["text"]

    def get_seen_ids(self) -> set[str]:
        with connect(self._path) as conn:
            return {row["video_id"] for row in conn.execute("SELECT video_id FROM songs")}

    def add_song(
        self,
        video_id: str,
        title: str,
        artist: str,
        url: str,
        description: str,
        query: str,
        taste_version: int,
    ) -> None:
        # An upsert, not INSERT OR REPLACE, which deletes the row and would trip feedback's foreign key.
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO songs (video_id, title, artist, url, description, query, taste_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET title = excluded.title, artist = excluded.artist, "
                "url = excluded.url, description = excluded.description, query = excluded.query, "
                "taste_version = excluded.taste_version, analyzed_at = CURRENT_TIMESTAMP",
                (video_id, title, artist, url, description, query, taste_version),
            )

    def list_songs(self) -> list[dict]:
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT video_id, title, artist, url, description, analyzed_at, taste_version, query "
                "FROM songs ORDER BY analyzed_at DESC, rowid DESC"
            )
            return [dict(row) for row in rows]
