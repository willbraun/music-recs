# Scoring

Status: planned, not implemented. Replaces the Music Flamingo YES/NO verdict in `api/analyze.py` and the artist-count "learned profile".

Every candidate clip is turned into an audio embedding, and a score from 0 to 1 says how well it matches the user's taste. The score starts from the genres in the [taste](taste.md) and moves toward the user's likes and dislikes as they rate songs. Ratings train a small classifier on top of frozen embeddings. The embedding model itself is never trained.

Related: [taste.md](taste.md), [database.md](database.md), [api.md](api.md), [song-card.md](song-card.md).

## Embeddings

- Model: `OpenMuQ/MuQ-MuLan-large`, a joint audio and text embedding model, loaded in `api/embed.py` (replacing `api/analyze.py`). Its weights are CC-BY-NC 4.0, which is fine for personal use. It runs in fp32 on CUDA, then MPS, then CPU.
- Input is 24 kHz mono audio. `CLIP_SECONDS` in [fetch.py](../api/fetch.py) becomes 40, and clips are written as 24 kHz mono WAV by the ffmpeg step in `_download_song`, so no resampling library is needed.
- `embed_audio(path)` splits the 40 second clip into four 10 second windows, embeds each, L2-normalizes each, averages them, and normalizes again. `embed_text(phrases)` embeds text the same way into the same space.
- Every analyzed song's embedding is stored in `song_embeddings` ([database.md](database.md#song_embeddings)), not only rated or recommended ones. The clip is deleted right after embedding, as before, so the stored embedding is the only trace of the audio.
- Embeddings are read into one numpy matrix when needed. There is no vector database or SQLite extension.

## Score

The scorer is built once at the start of a run, in `api/scorer.py`, from the taste and the rated songs. Ratings saved during a run apply to the next one.

### Taste prior

Each liked genre is embedded as a phrase with `embed_text`. The embeddings are averaged and normalized into a positive anchor. Disliked genres make a negative anchor the same way, and there is none when the list is empty. Artists are not used, because the text encoder does not know them, and negation is not used, because it does not understand it.

```
prior(x) = sigmoid((cos(x, positive) - cos(x, negative) - PRIOR_MID) / PRIOR_SCALE)
```

`cos(x, negative)` is 0 without a negative anchor. The prior is what scores songs before any ratings exist.

### Learned head

A logistic regression on the L2-normalized embeddings of rated songs: likes are 1 and dislikes are 0, with balanced class weights. Unrated songs are not used, and they are not treated as negatives. Only embeddings from the current model are used. The head is retrained from the database at the start of every run, and is never saved.

It is used only when there are at least `MIN_PER_CLASS` likes and `MIN_PER_CLASS` dislikes. Its output is the probability of a like.

### Blend and threshold

With `n` rated songs used for training:

```
w = n / (n + HEAD_HALF_RATINGS)
score = (1 - w) * prior + w * head
```

Without a head, `score = prior`. A song is **recommended** when `score >= threshold`, where the threshold falls as exploration rises:

```
threshold = THRESHOLD_STRICT - (THRESHOLD_STRICT - THRESHOLD_OPEN) * exploration / 100
```

Exploration also still sets the query tiers ([queries.py](../api/queries.py)).

### Constants

In `api/scorer.py`.

| Constant            | Value   | Meaning                                                    |
| ------------------- | ------- | ---------------------------------------------------------- |
| `MIN_PER_CLASS`     | 3       | Likes and dislikes each needed before the head is used     |
| `HEAD_HALF_RATINGS` | 20      | Rating count at which the head and the prior weigh equally |
| `THRESHOLD_STRICT`  | 0.7     | Recommend threshold at exploration 0                       |
| `THRESHOLD_OPEN`    | 0.4     | Recommend threshold at exploration 100                     |
| `PRIOR_MID`         | measure | Prior similarity that maps to 0.5                          |
| `PRIOR_SCALE`       | measure | Spread of the prior's sigmoid                              |

`PRIOR_MID` and `PRIOR_SCALE` are set once by measuring the prior similarity on the [backfilled](#existing-songs) songs, then fixed. The thresholds are starting values to adjust by hand against real recommendations.

## Rating songs

Each [song card](song-card.md) gets a like and a dislike toggle (`aria-pressed`, labeled). Only one can be active at a time.

- Clicking an inactive toggle saves that rating immediately, replacing the other one if it was active.
- Clicking the active toggle clears the rating.

A rating is only a like or a dislike, with no note or reason. Saving is an upsert, like `AppDb.add_song`, and re-rating resets `feedback.created_at`. The endpoints are in [api.md](api.md#songs).

## Search queries

[queries.py](../api/queries.py) generates queries from the taste text and the user's `RECENT_LIKES` (10) most recently liked songs, written as `Artist - Title`, ordered by `feedback.created_at`. The artists of those songs join the taste's liked artists in the pool of familiar fallback queries.

## Pipeline

[pipeline.py](../api/pipeline.py) `run`:

1. Load the taste, build the scorer, and read the seen ids.
2. Use the given query, or generate queries.
3. Download clips, and for each one embed it, score it, store the song with its embedding (recommended or not), and delete the clip.
4. Send a `scored` event with `score` and `recommended`. Stop once `count` songs are recommended.

`downloading_model` is sent for the embedding model and the query model only. `recommend.py` and `get_verdict` are removed, since there is no verdict string.

## Existing songs

Clips are not kept, so existing rated songs have no embeddings. `api/backfill_embeddings.py` is a CLI that, for each rated song without an embedding, downloads its clip with the same fetch code, embeds it, stores the embedding, and deletes the clip. Songs that no longer download are skipped and reported. Unrated songs are not backfilled, since only rated songs train the head.

## Tests

- `embed_audio`: window count and averaging, with the model stubbed. The output is normalized.
- Scorer: the prior ranks a song near the positive anchor above one near the negative anchor, and the head separates synthetic liked and disliked embeddings. It is not used below `MIN_PER_CLASS` of either class, and the blend weight follows `n / (n + HEAD_HALF_RATINGS)`. The threshold falls as exploration rises.
- `AppDb`: `add_song` writes the song and its embedding together, an embedding round-trips unchanged, and rated embeddings come back with their ratings.
- Pipeline: every analyzed song is stored with its embedding and `recommended`, clips are deleted after embedding, the run stops after `count` recommendations, and `scored` carries `score`.
- Queries: recent liked songs appear in the prompt, and their artists join the fallback pool.
- Feedback endpoints: `PUT` creates and updates, `DELETE` clears, and a re-rating resets `created_at`.
- Rating UI: clicking an inactive toggle saves that rating, clicking the active one clears it, and switching from like to dislike replaces the rating.

## Non-goals

- Fine-tuning the embedding model.
- A vector database or SQLite extension.
- Hard rules. Disliked genres are only a soft negative in the prior, and explicit exclusions and language requirements are not enforced.
- Rating notes or reasons.
- Treating unrated songs as negatives.
- Showing or explaining the score beyond the badge on the card.
