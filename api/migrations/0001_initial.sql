-- Baseline schema. An app.db from before migrations may already have taste_versions.
CREATE TABLE IF NOT EXISTS taste_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE songs (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL,
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    taste_version INTEGER REFERENCES taste_versions (id),
    query TEXT
);

-- rating: 1 = like, -1 = dislike.
CREATE TABLE feedback (
    video_id TEXT PRIMARY KEY REFERENCES songs (video_id) ON DELETE RESTRICT,
    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
