import re
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILE_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")


def _load_migrations(directory: Path) -> list[tuple[int, Path]]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_NAME.match(path.name)
        if match is None:
            raise ValueError(f"Migration file names must look like 0001_name.sql, got {path.name}")
        migrations.append((int(match[1]), path))
    if [version for version, _ in migrations] != list(range(1, len(migrations) + 1)):
        raise ValueError("Migration numbers must start at 1 and have no gaps or duplicates")
    return migrations


def apply_migrations(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> None:
    """Run each migration newer than `PRAGMA user_version`, one transaction per file."""
    migrations = _load_migrations(directory)
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current > len(migrations):
        raise RuntimeError(f"Database is at version {current}, but only {len(migrations)} migrations exist")

    # WAL lets feedback writes proceed while the pipeline writes songs; it persists in the file.
    conn.execute("PRAGMA journal_mode=WAL")

    for version, path in migrations[current:]:
        # executescript commits first, so BEGIN/COMMIT here makes the file and the version bump atomic.
        script = f"BEGIN;\n{path.read_text()}\nPRAGMA user_version = {version};\nCOMMIT;"
        try:
            conn.executescript(script)
        except Exception:
            conn.rollback()
            raise
