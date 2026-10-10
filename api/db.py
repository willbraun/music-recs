import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path) -> Generator[sqlite3.Connection]:
    # One connection per operation, so the API's worker and request threads never share one.
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # Off by default and per connection; cannot be changed inside a transaction.
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()
