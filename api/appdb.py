from pathlib import Path

from db import connect
from migrate import apply_migrations
from taste_profile import Taste, TasteProfile

DB_PATH = Path(__file__).parent / "app.db"


def get_artist_key(artist: str) -> str:
    """Normalize to the lead artist, since collaborations are credited as "Lead, Guest"."""
    return artist.split(",")[0].strip().casefold()


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

    def get_recommended_artist_counts(self, limit: int) -> dict[str, int]:
        """Count the last `limit` recommended songs per lead artist, keyed by the artist's most recent name."""
        names: dict[str, str] = {}
        counts: dict[str, int] = {}
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT artist FROM songs WHERE verdict = 1 ORDER BY analyzed_at DESC, rowid DESC LIMIT ?", (limit,)
            )
            for row in rows:
                key = get_artist_key(row["artist"])
                names.setdefault(key, row["artist"].split(",")[0].strip())
                counts[key] = counts.get(key, 0) + 1
        return {names[key]: count for key, count in counts.items()}

    def add_song(
        self,
        video_id: str,
        title: str,
        artist: str,
        url: str,
        verdict: bool,
        confidence: float,
        query: str,
        *,
        thumbnail_url: str | None = None,
        album_art_url: str | None = None,
        album: str | None = None,
        musicbrainz_recording_id: str | None = None,
        musicbrainz_release_group_id: str | None = None,
    ) -> None:
        # An upsert, not INSERT OR REPLACE, which deletes the row first.
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO songs (video_id, title, artist, url, verdict, confidence, query, thumbnail_url, "
                "album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (video_id) DO UPDATE SET title = excluded.title, artist = excluded.artist, "
                "url = excluded.url, verdict = excluded.verdict, confidence = excluded.confidence, "
                "query = excluded.query, thumbnail_url = excluded.thumbnail_url, "
                "album_art_url = excluded.album_art_url, album = excluded.album, "
                "musicbrainz_recording_id = excluded.musicbrainz_recording_id, "
                "musicbrainz_release_group_id = excluded.musicbrainz_release_group_id, "
                "analyzed_at = CURRENT_TIMESTAMP",
                (
                    video_id,
                    title,
                    artist,
                    url,
                    verdict,
                    confidence,
                    query,
                    thumbnail_url,
                    album_art_url,
                    album,
                    musicbrainz_recording_id,
                    musicbrainz_release_group_id,
                ),
            )

    def list_songs(self) -> list[dict]:
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT video_id, title, artist, url, verdict, confidence, analyzed_at, query, thumbnail_url, "
                "album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id "
                "FROM songs ORDER BY analyzed_at DESC, rowid DESC"
            )
            songs = [dict(row) for row in rows]
        for song in songs:
            song["recommended"] = bool(song.pop("verdict"))
        return songs
