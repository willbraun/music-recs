import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILE_NAME = re.compile(r"^(\d{14})_[a-z0-9_]+\.sql$")


def _load_migrations(directory: Path) -> list[tuple[int, Path]]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_NAME.match(path.name)
        if match is None:
            raise ValueError(f"Migration file names must look like YYYYMMDDHHMMSS_name.sql, got {path.name}")
        migrations.append((int(match[1]), path))
    versions = [version for version, _ in migrations]
    if len(set(versions)) != len(versions):
        raise ValueError("Migration timestamps must be unique")
    return migrations


def apply_migrations(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> None:
    """Run each migration not yet recorded in `schema_migrations`, one transaction per file."""
    migrations = _load_migrations(directory)

    # WAL lets API reads proceed while the pipeline writes songs; it persists in the file.
    conn.execute("PRAGMA journal_mode=WAL")
    # PRAGMA user_version is a 32-bit integer and cannot hold a 14-digit timestamp.
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)")

    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    unknown = applied - {version for version, _ in migrations}
    if unknown:
        raise RuntimeError(f"Database has migrations this code does not know about: {sorted(unknown)}")

    for version, path in migrations:
        if version in applied:
            continue
        # executescript commits first, so BEGIN/COMMIT here makes the file and its record atomic.
        script = f"BEGIN;\n{path.read_text()}\nINSERT INTO schema_migrations (version) VALUES ({version});\nCOMMIT;"
        try:
            conn.executescript(script)
        except Exception:
            conn.rollback()
            raise
