-- verdict: 1 = the model said YES, 0 = NO. confidence: probability of that answer, 0.5 to 1.
CREATE TABLE songs (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    verdict INTEGER NOT NULL CHECK (verdict IN (0, 1)),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0.5 AND 1),
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query TEXT
);

-- The user's current taste. id is fixed so the table holds one row; profile is the JSON of the entered fields.
CREATE TABLE taste (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    profile TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
