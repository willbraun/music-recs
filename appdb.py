from pathlib import Path

from db import connect

DB_PATH = Path(__file__).parent / "app.db"

SEED_TASTE = "Electronic, dance, 2010's indie rock/pop, synthpop, grunge, hip hop, rock, blues, bluegrass, melodic metal. No country, world, Christian, or children's music. My favorite artists are Tame Impala, Cherub, New Order, Opeth, BORNS, GROUPLOVE, The Black Keys, Glass Animals, Todd Terge, Mac Miller, Flume, The Cranberries. If songs have lyrics, they should be in English."


class AppDb:
    """Data that must survive deleting cache.db: taste history and song feedback."""

    def __init__(self, path: Path = DB_PATH):
        self._path = path
        with connect(path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS taste_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Song details are copied here so feedback stays useful after the cache is wiped.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT NOT NULL,
                    taste_version INTEGER,
                    rating INTEGER NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            if "model_score" in {row["name"] for row in conn.execute("PRAGMA table_info(feedback)")}:
                conn.execute("ALTER TABLE feedback DROP COLUMN model_score")
            if conn.execute("SELECT 1 FROM taste_versions").fetchone() is None:
                conn.execute("INSERT INTO taste_versions (text, source) VALUES (?, 'seed')", (SEED_TASTE,))

    def get_current_taste(self) -> tuple[int, str]:
        with connect(self._path) as conn:
            row = conn.execute("SELECT id, text FROM taste_versions ORDER BY id DESC LIMIT 1").fetchone()
            return row["id"], row["text"]

    def get_rated_ids(self) -> set[str]:
        with connect(self._path) as conn:
            return {row["video_id"] for row in conn.execute("SELECT video_id FROM feedback")}
