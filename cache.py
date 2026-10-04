from pathlib import Path

from db import connect

DB_PATH = Path(__file__).parent / "cache.db"

# Columns added after the first release; older databases get them via ALTER TABLE.
_ADDED_COLUMNS = {"taste_version": "INTEGER", "query": "TEXT"}


class Cache:
    def __init__(self, path: Path = DB_PATH):
        self._path = path
        with connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS songs (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT NOT NULL,
                    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    taste_version INTEGER,
                    query TEXT
                )
                """
            )
            existing = {row["name"] for row in conn.execute("PRAGMA table_info(songs)")}
            for name, column_type in _ADDED_COLUMNS.items():
                if name not in existing:
                    conn.execute(f"ALTER TABLE songs ADD COLUMN {name} {column_type}")
            if "score" in existing:
                conn.execute("ALTER TABLE songs DROP COLUMN score")

    def seen_ids(self) -> set[str]:
        with connect(self._path) as conn:
            return {row["video_id"] for row in conn.execute("SELECT video_id FROM songs")}

    def add(
        self,
        video_id: str,
        title: str,
        artist: str,
        url: str,
        description: str,
        query: str,
        taste_version: int,
    ) -> None:
        with connect(self._path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO songs (video_id, title, artist, url, description, query, taste_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (video_id, title, artist, url, description, query, taste_version),
            )

    def list_songs(self) -> list[dict]:
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT video_id, title, artist, url, description, analyzed_at, taste_version, query "
                "FROM songs ORDER BY analyzed_at DESC, rowid DESC"
            )
            return [dict(row) for row in rows]
