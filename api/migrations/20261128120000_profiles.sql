-- avatar: a single emoji. Songs and taste belong to a profile; profile_id 0 marks rows from before profiles existed,
-- which the first profile created adopts. There is no foreign key, so AppDb.delete_profile removes a profile's rows.
CREATE TABLE profiles (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    avatar TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE songs_new (
    profile_id INTEGER NOT NULL,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    url TEXT NOT NULL,
    verdict INTEGER NOT NULL CHECK (verdict IN (0, 1)),
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0.5 AND 1),
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    query TEXT,
    thumbnail_url TEXT,
    album_art_url TEXT,
    album TEXT,
    musicbrainz_recording_id TEXT,
    musicbrainz_release_group_id TEXT,
    PRIMARY KEY (profile_id, video_id)
);

INSERT INTO songs_new (
    profile_id, video_id, title, artist, url, verdict, confidence, analyzed_at, query, thumbnail_url,
    album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id
)
SELECT
    0, video_id, title, artist, url, verdict, confidence, analyzed_at, query, thumbnail_url,
    album_art_url, album, musicbrainz_recording_id, musicbrainz_release_group_id
FROM songs ORDER BY rowid;

DROP TABLE songs;
ALTER TABLE songs_new RENAME TO songs;

-- profile is the JSON of the entered fields.
CREATE TABLE taste_new (
    profile_id INTEGER PRIMARY KEY,
    profile TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO taste_new (profile_id, profile, updated_at) SELECT 0, profile, updated_at FROM taste;

DROP TABLE taste;
ALTER TABLE taste_new RENAME TO taste;
