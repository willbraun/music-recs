# music-recs

Finds new studio songs on YouTube Music for a search query, describes each one with an audio model, and scores it against your taste. Songs scoring at or above a threshold are printed as recommendations.

## How it works

1. **Fetch** ([fetch.py](fetch.py)): searches YouTube Music for the query, filters out non-studio versions, and downloads a 60-second clip from the middle of each track as WAV.
2. **Analyze** ([analyze.py](analyze.py)): the `nvidia/music-flamingo-2601-hf` model writes a short description of the clip (genre, tempo, key, instruments, production, mood).
3. **Score** ([recommend.py](recommend.py)): the description is scored with `laya` against the taste profile in `TASTE`.
4. **Cache** ([cache.py](cache.py)): every analyzed song is saved to a local SQLite database.

The next clip downloads while the current one is being analyzed.

## Requirements

- Python 3.13 (other recent versions may work)
- [ffmpeg](https://ffmpeg.org/) on your `PATH` (yt-dlp uses it to cut and convert clips)
- Enough memory to run the model; the code is written for Apple Silicon (MPS) but uses `device_map="auto"`
- Whatever credentials or configuration `laya`'s `Router` needs for scoring

## Setup

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The model is downloaded from Hugging Face on first run.

## Usage

```sh
python main.py "indie rock"
python main.py "The Cranberries" --count 10 --threshold 0.7
```

| Argument      | Default | Description                                          |
| ------------- | ------- | ---------------------------------------------------- |
| `query`       | -       | Search query (artist, genre, mood, etc.)             |
| `--count`     | `5`     | Number of new tracks to analyze                      |
| `--threshold` | `0.5`   | Minimum score (0 to 1) for a track to be recommended |

Example output:

```
[1/5] Artist - Title
...

Recommended (2 of 5 new tracks):
  0.91  Artist - Title  https://www.youtube.com/watch?v=...
```

Recommendations are sorted by score, highest first.

## Cache behavior

- Results are stored in `cache.db` (SQLite) next to the scripts, in a `songs` table with the video id, title, artist, URL, score, description, and analysis time.
- A song is saved right after it is analyzed, so an interrupted run keeps the songs it finished.
- Songs already in the cache are skipped during search. They are not downloaded, analyzed, or scored again, and they never appear in later results, even if they scored above the threshold.
- Because skipped songs come out of the search results, a query you have run many times may return fewer than `--count` new tracks.
- The cache does not expire. To start fresh, delete `cache.db`. To re-analyze one song, delete its row:

  ```sh
  sqlite3 cache.db "DELETE FROM songs WHERE video_id = '<id>'"
  ```

- To review past results:

  ```sh
  sqlite3 cache.db "SELECT score, artist, title, url FROM songs ORDER BY score DESC"
  ```

Changing the prompt, the taste profile, or the model does not update existing cache entries; their scores stay as they were.

## Song filtering

Only studio recordings are kept. A track is skipped if:

- its title, track name, or album has a qualifier such as live, remix, cover, acoustic, karaoke, instrumental, sped up, slowed, reverb, mix, session, version, podcast, mashup, nightcore, or 8d
- it has no track or artist metadata
- it is shorter than 90 seconds or longer than 8 minutes
- it has fewer than 1,000 views
- its title, description, uploader, or tags mention AI generation (for example Suno, Udio, "AI generated", "made with AI")

Search fetches three times `--count` results to leave room for skipped tracks.

## Temporary files

Clips are written to a temporary directory (`music-recs-*` under your system temp folder). Each clip is deleted after it is analyzed, and the directory is removed when the run ends.

## Customizing

| What                               | Where                                                               |
| ---------------------------------- | ------------------------------------------------------------------- |
| Taste profile and scoring question | `TASTE` and `QUESTIONS` in [recommend.py](recommend.py)             |
| Description prompt and length      | `PROMPT` and `MAX_NEW_TOKENS` in [analyze.py](analyze.py)           |
| Clip length                        | `CLIP_SECONDS` in [fetch.py](fetch.py)                              |
| Duration limits, search overfetch  | `MIN_DURATION`, `MAX_DURATION`, `OVERFETCH` in [fetch.py](fetch.py) |
| Minimum view count                 | `MIN_VIEWS` in [fetch.py](fetch.py)                                 |
| Excluded keywords                  | `NON_STUDIO`, `AI_GENERATED` in [fetch.py](fetch.py)                |

## Notes

- The first analysis is slow because the model has to load; later tracks in the same run are faster.
- On MPS the rotary embedding is patched to float32 in [analyze.py](analyze.py), since MPS has no float64 support.
# music-recs
