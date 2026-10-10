from pathlib import Path

from db import connect
from migrate import apply_migrations
from taste_profile import Taste, TasteProfile

DB_PATH = Path(__file__).parent / "app.db"


class AppDb:
    """Songs and the user's taste. Schema changes go in api/migrations."""

    def __init__(self, path: Path = DB_PATH):
        self._path = path
        with connect(path) as conn:
            apply_migrations(conn)

    def get_current_taste(self) -> Taste | None:
        with connect(self._path) as conn:
            row = conn.execute("SELECT profile, updated_at FROM taste WHERE id = 1").fetchone()
        if row is None:
            return None
        return Taste(TasteProfile.model_validate_json(row["profile"]), row["updated_at"])

    def save_taste(self, profile: TasteProfile) -> Taste:
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO taste (id, profile) VALUES (1, ?) "
                "ON CONFLICT (id) DO UPDATE SET profile = excluded.profile, updated_at = CURRENT_TIMESTAMP",
                (profile.model_dump_json(),),
            )
            row = conn.execute("SELECT updated_at FROM taste WHERE id = 1").fetchone()
        return Taste(profile, row["updated_at"])

    def get_seen_ids(self) -> set[str]:
        with connect(self._path) as conn:
            return {row["video_id"] for row in conn.execute("SELECT video_id FROM songs")}

    def add_song(
        self,
        video_id: str,
        title: str,
        artist: str,
        url: str,
        verdict: bool,
        confidence: float,
        query: str,
    ) -> None:
        # An upsert, not INSERT OR REPLACE, which deletes the row first.
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO songs (video_id, title, artist, url, verdict, confidence, query) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET title = excluded.title, artist = excluded.artist, "
                "url = excluded.url, verdict = excluded.verdict, confidence = excluded.confidence, "
                "query = excluded.query, analyzed_at = CURRENT_TIMESTAMP",
                (video_id, title, artist, url, verdict, confidence, query),
            )

    def list_songs(self) -> list[dict]:
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT video_id, title, artist, url, verdict, confidence, analyzed_at, query "
                "FROM songs ORDER BY analyzed_at DESC, rowid DESC"
            )
            songs = [dict(row) for row in rows]
        for song in songs:
            song["recommended"] = bool(song.pop("verdict"))
        return songs
