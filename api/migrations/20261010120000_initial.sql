CREATE TABLE songs (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    score REAL NOT NULL CHECK (score BETWEEN 0 AND 1),
    recommended INTEGER NOT NULL CHECK (recommended IN (0, 1)),
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query TEXT NOT NULL
);

CREATE TABLE taste (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    profile TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE song_embeddings (
    video_id TEXT PRIMARY KEY REFERENCES songs (video_id),
    model TEXT NOT NULL,
    embedding BLOB NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- rating: 1 = like, -1 = dislike.
CREATE TABLE feedback (
    video_id TEXT PRIMARY KEY REFERENCES songs (video_id) ON DELETE RESTRICT,
    rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
