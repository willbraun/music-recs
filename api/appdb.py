from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from db import connect
from migrate import apply_migrations
from taste_profile import TasteProfile

DB_PATH = Path(__file__).parent / "app.db"

SortOrder = Literal["newest", "oldest"]

_ORDER_BY: dict[SortOrder, str] = {
    "newest": "s.analyzed_at DESC, s.rowid DESC",
    "oldest": "s.analyzed_at ASC, s.rowid ASC",
}


@dataclass
class Taste:
    profile: TasteProfile
    updated_at: str


def _serialize_embedding(embedding: np.ndarray) -> bytes:
    return np.asarray(embedding, dtype="<f4").tobytes()


def _deserialize_embedding(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4")


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_song_filter(recommended: bool | None, q: str | None) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if recommended is not None:
        clauses.append("s.recommended = ?")
        params.append(int(recommended))
    if q is not None:
        # Album is matched too once the column exists (specs/artwork.md).
        clauses.append("(s.title LIKE ? ESCAPE '\\' OR s.artist LIKE ? ESCAPE '\\')")
        params += [f"%{_escape_like(q)}%"] * 2
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


class AppDb:
    """Songs, taste, embeddings, and song feedback. Schema changes go in api/migrations."""

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
        score: float,
        recommended: bool,
        query: str,
        embedding: np.ndarray,
        model: str,
    ) -> None:
        # An upsert, not INSERT OR REPLACE, which deletes the row and would trip feedback's foreign key.
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO songs (video_id, title, artist, url, score, recommended, query) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET title = excluded.title, artist = excluded.artist, "
                "url = excluded.url, score = excluded.score, recommended = excluded.recommended, "
                "query = excluded.query, analyzed_at = CURRENT_TIMESTAMP",
                (video_id, title, artist, url, score, int(recommended), query),
            )
            conn.execute(
                "INSERT INTO song_embeddings (video_id, model, embedding) VALUES (?, ?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET model = excluded.model, embedding = excluded.embedding, "
                "created_at = CURRENT_TIMESTAMP",
                (video_id, model, _serialize_embedding(embedding)),
            )

    def list_songs(
        self,
        recommended: bool | None = None,
        q: str | None = None,
        sort: SortOrder = "newest",
        limit: int = 24,
        offset: int = 0,
    ) -> list[dict]:
        where, params = _build_song_filter(recommended, q)
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT s.video_id, s.title, s.artist, s.url, s.score, s.recommended, s.analyzed_at, s.query, "
                "f.rating FROM songs s LEFT JOIN feedback f ON f.video_id = s.video_id"
                f"{where} ORDER BY {_ORDER_BY[sort]} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
            return [{**row, "recommended": bool(row["recommended"])} for row in map(dict, rows)]

    def count_songs(self, recommended: bool | None = None, q: str | None = None) -> int:
        where, params = _build_song_filter(recommended, q)
        with connect(self._path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM songs s{where}", params).fetchone()[0]

    def get_rated_embeddings(self, model: str) -> list[tuple[np.ndarray, int]]:
        """Return (embedding, rating) for rated songs embedded by `model`."""
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT e.embedding, f.rating FROM feedback f JOIN song_embeddings e ON e.video_id = f.video_id "
                "WHERE e.model = ? ORDER BY f.created_at, f.rowid",
                (model,),
            ).fetchall()
        return [(_deserialize_embedding(row["embedding"]), row["rating"]) for row in rows]

    def get_artist_embeddings(self, model: str) -> list[tuple[str, np.ndarray]]:
        """Return (artist, embedding) for every song embedded by `model` that is not disliked."""
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT s.artist, e.embedding FROM songs s JOIN song_embeddings e ON e.video_id = s.video_id "
                "LEFT JOIN feedback f ON f.video_id = s.video_id "
                "WHERE e.model = ? AND (f.rating IS NULL OR f.rating = 1)",
                (model,),
            ).fetchall()
        return [(row["artist"], _deserialize_embedding(row["embedding"])) for row in rows]

    def get_recent_likes(self, limit: int) -> list[tuple[str, str]]:
        """Return (artist, title) of the most recently liked songs, newest first."""
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT s.artist, s.title FROM feedback f JOIN songs s ON s.video_id = f.video_id "
                "WHERE f.rating = 1 ORDER BY f.created_at DESC, f.rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(row["artist"], row["title"]) for row in rows]

    def set_feedback(self, video_id: str, rating: int) -> dict | None:
        """Save a rating, replacing any earlier one; returns None when the song does not exist."""
        with connect(self._path) as conn:
            if conn.execute("SELECT 1 FROM songs WHERE video_id = ?", (video_id,)).fetchone() is None:
                return None
            conn.execute(
                "INSERT INTO feedback (video_id, rating) VALUES (?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET rating = excluded.rating, created_at = CURRENT_TIMESTAMP",
                (video_id, rating),
            )
            row = conn.execute("SELECT video_id, rating, created_at FROM feedback WHERE video_id = ?", (video_id,))
            return dict(row.fetchone())

    def clear_feedback(self, video_id: str) -> bool:
        """Remove a song's rating; returns False when the song does not exist."""
        with connect(self._path) as conn:
            if conn.execute("SELECT 1 FROM songs WHERE video_id = ?", (video_id,)).fetchone() is None:
                return False
            conn.execute("DELETE FROM feedback WHERE video_id = ?", (video_id,))
            return True
