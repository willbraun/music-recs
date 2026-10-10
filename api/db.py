import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    # One connection per operation, so the API's worker and request threads never share one.
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()
