-- Baseline schema.
CREATE TABLE taste_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- verdict: 1 = the model said YES, 0 = NO. confidence: probability of that answer, 0.5 to 1.
CREATE TABLE songs (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    verdict INTEGER NOT NULL CHECK (verdict IN (0, 1)),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0.5 AND 1),
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
