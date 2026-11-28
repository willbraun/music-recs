from pathlib import Path

from db import connect
from migrate import apply_migrations
from paths import get_data_dir
from taste_profile import Taste, TasteProfile

DB_FILE_NAME = "app.db"


def get_artist_key(artist: str) -> str:
    """Normalize to the lead artist, since collaborations are credited as "Lead, Guest"."""
    return artist.split(",")[0].strip().casefold()


class AppDb:
    """Profiles, and each profile's songs and taste. Schema changes go in api/migrations."""

    def __init__(self, path: Path | None = None):
        path = path or get_data_dir() / DB_FILE_NAME
        self._path = path
        with connect(path) as conn:
            apply_migrations(conn)

    def list_profiles(self) -> list[dict]:
        with connect(self._path) as conn:
            return [dict(row) for row in conn.execute("SELECT id, name, avatar FROM profiles ORDER BY id")]

    def get_profile(self, profile_id: int) -> dict | None:
        with connect(self._path) as conn:
            row = conn.execute("SELECT id, name, avatar FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return None if row is None else dict(row)

    def add_profile(self, name: str, avatar: str) -> dict:
        with connect(self._path) as conn:
            is_first = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
            profile_id = conn.execute("INSERT INTO profiles (name, avatar) VALUES (?, ?)", (name, avatar)).lastrowid
            if is_first:
                # Songs and taste from before profiles existed belong to the first profile.
                conn.execute("UPDATE songs SET profile_id = ? WHERE profile_id = 0", (profile_id,))
                conn.execute("UPDATE taste SET profile_id = ? WHERE profile_id = 0", (profile_id,))
        return {"id": profile_id, "name": name, "avatar": avatar}

    def update_profile(self, profile_id: int, name: str, avatar: str) -> dict | None:
        with connect(self._path) as conn:
            changed = conn.execute(
                "UPDATE profiles SET name = ?, avatar = ? WHERE id = ?", (name, avatar, profile_id)
            ).rowcount
        return {"id": profile_id, "name": name, "avatar": avatar} if changed else None

    def delete_profile(self, profile_id: int) -> bool:
        with connect(self._path) as conn:
            conn.execute("DELETE FROM songs WHERE profile_id = ?", (profile_id,))
            conn.execute("DELETE FROM taste WHERE profile_id = ?", (profile_id,))
            return conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,)).rowcount > 0

    def get_current_taste(self, profile_id: int) -> Taste | None:
        # Only the profile fields are stored; Taste.text is rendered on read so the two cannot disagree.
        with connect(self._path) as conn:
            row = conn.execute("SELECT profile, updated_at FROM taste WHERE profile_id = ?", (profile_id,)).fetchone()
        if row is None:
            return None
        return Taste(TasteProfile.model_validate_json(row["profile"]), row["updated_at"])

    def save_taste(self, profile_id: int, profile: TasteProfile) -> Taste:
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO taste (profile_id, profile) VALUES (?, ?) "
                "ON CONFLICT (profile_id) DO UPDATE SET profile = excluded.profile, updated_at = CURRENT_TIMESTAMP",
                (profile_id, profile.model_dump_json()),
            )
            row = conn.execute("SELECT updated_at FROM taste WHERE profile_id = ?", (profile_id,)).fetchone()
        return Taste(profile, row["updated_at"])

    def get_seen_ids(self, profile_id: int) -> set[str]:
        # Every analyzed song is stored, recommended or not, so searches skip by video_id alone.
        with connect(self._path) as conn:
            rows = conn.execute("SELECT video_id FROM songs WHERE profile_id = ?", (profile_id,))
            return {row["video_id"] for row in rows}

    def get_recommended_artist_counts(self, profile_id: int, limit: int) -> dict[str, int]:
        """Count the profile's last `limit` recommended songs per lead artist, keyed by the artist's most recent name."""
        names: dict[str, str] = {}
        counts: dict[str, int] = {}
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT artist FROM songs WHERE profile_id = ? AND verdict = 1 "
                "ORDER BY analyzed_at DESC, rowid DESC LIMIT ?",
                (profile_id, limit),
            )
            for row in rows:
                key = get_artist_key(row["artist"])
                names.setdefault(key, row["artist"].split(",")[0].strip())
                counts[key] = counts.get(key, 0) + 1
        return {names[key]: count for key, count in counts.items()}

    def add_song(
        self,
        profile_id: int,
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
        # An upsert, not INSERT OR REPLACE, which deletes the row first. Re-adding resets analyzed_at.
        with connect(self._path) as conn:
            conn.execute(
                "INSERT INTO songs (profile_id, video_id, title, artist, url, verdict, confidence, query, thumbnail_url, "
                "album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (profile_id, video_id) DO UPDATE SET title = excluded.title, artist = excluded.artist, "
                "url = excluded.url, verdict = excluded.verdict, confidence = excluded.confidence, "
                "query = excluded.query, thumbnail_url = excluded.thumbnail_url, "
                "album_art_url = excluded.album_art_url, album = excluded.album, "
                "musicbrainz_recording_id = excluded.musicbrainz_recording_id, "
                "musicbrainz_release_group_id = excluded.musicbrainz_release_group_id, "
                "analyzed_at = CURRENT_TIMESTAMP",
                (
                    profile_id,
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

    def count_songs(self, profile_id: int) -> int:
        with connect(self._path) as conn:
            return conn.execute("SELECT COUNT(*) FROM songs WHERE profile_id = ?", (profile_id,)).fetchone()[0]

    def list_songs(self, profile_id: int, limit: int = -1, offset: int = 0) -> list[dict]:
        """Newest first. A negative `limit` (SQLite's LIMIT -1) means no limit."""
        with connect(self._path) as conn:
            rows = conn.execute(
                "SELECT video_id, title, artist, url, verdict, confidence, analyzed_at, query, thumbnail_url, "
                "album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id "
                "FROM songs WHERE profile_id = ? ORDER BY analyzed_at DESC, rowid DESC LIMIT ? OFFSET ?",
                (profile_id, limit, offset),
            )
            songs = [dict(row) for row in rows]
        # The column is `verdict`; the API calls it `recommended`.
        for song in songs:
            song["recommended"] = bool(song.pop("verdict"))
        return songs
