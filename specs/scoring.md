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

Each liked genre is embedded as a phrase with `embed_text`. The embeddings are averaged and normalized into a positive anchor. Disliked genres make a negative anchor the same way, and there is none when the list is empty. Artist names are not embedded as text, because the text encoder does not know them (measured: the text embedding of "Tame Impala" did not rank Tame Impala's own songs near the top), and negation is not used, because it does not understand it. Disliked artists are a hard filter against searches.

```
genre_prior(x) = sigmoid((cos(x, positive) - cos(x, negative) - PRIOR_MID) / PRIOR_SCALE)
```

`cos(x, negative)` is 0 without a negative anchor.

### Artist prior

Liked artists are used through the audio of their songs. The artist anchor is the normalized mean of the normalized embeddings of every analyzed song by a liked artist, excluding songs the user disliked. A song's artist matches a liked artist when the name is equal ignoring case, or is one of several joined by `,`, `/`, or `&` (`is_artist_match` in [fetch.py](../api/fetch.py)). There is no artist anchor when no such song exists.

```
artist_prior(x) = sigmoid((cos(x, artist_anchor) - ARTIST_MID) / ARTIST_SCALE)
prior(x) = max(genre_prior(x), artist_prior(x))
```

The two are separate terms because audio-to-audio similarity is on a much higher scale than audio-to-text similarity, so one anchor cannot serve both. The prior is what scores songs before any ratings exist.

### Seeding liked artists

At the start of a run, each liked artist with fewer than `SEED_SONGS_PER_ARTIST` (3) analyzed songs gets the missing ones from a search for the artist's name. `fetch_songs` takes a `required_artist` and rejects other artists' songs, covers, and anything not a studio song before the clip is downloaded. The clips are embedded and deleted like any other.

Seed songs are stored as ordinary songs once the scorer is built, scored by it like any other, with the artist as their `query`. They appear on the Songs page and are never fetched again. They do not produce `scored` events and are not part of the run's results. Artists with no usable songs are retried on the next run.

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

| Constant                | Value | Meaning                                                    |
| ----------------------- | ----- | ---------------------------------------------------------- |
| `MIN_PER_CLASS`         | 3     | Likes and dislikes each needed before the head is used     |
| `HEAD_HALF_RATINGS`     | 20    | Rating count at which the head and the prior weigh equally |
| `THRESHOLD_STRICT`      | 0.7   | Recommend threshold at exploration 0                       |
| `THRESHOLD_OPEN`        | 0.4   | Recommend threshold at exploration 100                     |
| `PRIOR_MID`             | 0.07  | Genre similarity that maps to 0.5                          |
| `PRIOR_SCALE`           | 0.04  | Spread of the genre prior's sigmoid                        |
| `ARTIST_MID`            | 0.6   | Artist similarity that maps to 0.5                         |
| `ARTIST_SCALE`          | 0.08  | Spread of the artist prior's sigmoid                       |
| `SEED_SONGS_PER_ARTIST` | 3     | Analyzed songs wanted per liked artist (`pipeline.py`)     |

`PRIOR_MID` and `PRIOR_SCALE` were set by measuring the genre similarity on 23 analyzed songs (cosine to the anchor ranged from -0.13 to 0.16, mean 0.02), then fixed; re-measure on a larger sample. `ARTIST_MID` and `ARTIST_SCALE` were measured on 46 songs: audio cosine to the mean of the same artist's other songs averaged 0.63, against 0.46 for other artists' songs (90th percentile 0.71). That separation is modest. The thresholds are starting values to adjust by hand against real recommendations.

## Rating songs

Each [song card](song-card.md) gets a like and a dislike toggle (`aria-pressed`, labeled). Only one can be active at a time.

- Clicking an inactive toggle saves that rating immediately, replacing the other one if it was active.
- Clicking the active toggle clears the rating.

A rating is only a like or a dislike, with no note or reason. Saving is an upsert, like `AppDb.add_song`, and re-rating resets `feedback.created_at`. The endpoints are in [api.md](api.md#songs).

## Search queries

[queries.py](../api/queries.py) generates queries from the taste text and the user's `RECENT_LIKES` (10) most recently liked songs, written as `Artist - Title`, ordered by `feedback.created_at`. The artists of those songs join the taste's liked artists in the pool of familiar fallback queries.

## Pipeline

[pipeline.py](../api/pipeline.py) `run`:

1. Load the taste and read the seen ids.
2. Use the given query, or generate queries.
3. [Seed](#seeding-liked-artists) liked artists that have too few analyzed songs, then build the scorer from the taste, the ratings, and the songs by liked artists. Seed songs are stored.
4. Search and download clips. `fetch_songs` rejects a candidate whose artist is in the taste's `disliked_artists` (ignoring case) with its other metadata checks, before its clip is downloaded. Rejected songs are not stored.
5. For each clip, embed it, score it, store the song with its embedding (recommended or not), and delete the clip. A song is recommended only if its score meets the threshold and no song by the same primary artist (the first of a name joined by `,`, `/`, or `&`, ignoring case) was already recommended in this run, so one favorite artist cannot fill a batch. Such a song is stored as not recommended.
6. Send a `scored` event with `score` and `recommended`. Stop once `count` songs are recommended.

A `seeding` event with the artist's name is sent before each artist is seeded. `downloading_model` is sent for the embedding model and the query model only. `recommend.py` and `get_verdict` are removed, since there is no verdict string.

## Tests

- `embed_audio`: window count and averaging, with the model stubbed. The output is normalized.
- Scorer: the prior ranks a song near the positive anchor above one near the negative anchor, and the head separates synthetic liked and disliked embeddings. It is not used below `MIN_PER_CLASS` of either class, and the blend weight follows `n / (n + HEAD_HALF_RATINGS)`. The threshold falls as exploration rises. Songs by liked artists raise the prior of similar songs, and there is no artist anchor without them.
- `AppDb`: `add_song` writes the song and its embedding together, an embedding round-trips unchanged, rated embeddings come back with their ratings, and artist embeddings leave out disliked songs and other models.
- Pipeline: every analyzed song is stored with its embedding and `recommended`, clips are deleted after embedding, the run stops after `count` recommendations, and `scored` carries `score`. Liked artists with too few songs are seeded for only the missing count, artists with enough are not, and seed songs are stored, scored against the threshold, and not sent as `scored` events. A run recommends at most one song per artist, including joined and differently cased names.
- Queries: recent liked songs appear in the prompt, and their artists join the fallback pool.
- Fetch: a candidate by a disliked artist is rejected before its clip is downloaded, ignoring case. With `required_artist`, other artists' songs are rejected the same way, and `is_artist_match` handles joined artist names.
- Feedback endpoints: `PUT` creates and updates, `DELETE` clears, and a re-rating resets `created_at`.
- Rating UI: clicking an inactive toggle saves that rating, clicking the active one clears it, and switching from like to dislike replaces the rating.

## Non-goals

- Fine-tuning the embedding model.
- A vector database or SQLite extension.
- Hard rules beyond disliked artists. Disliked genres are only a soft negative in the prior, and language requirements are not enforced.
- Rating notes or reasons.
- Treating unrated songs as negatives.
- Showing or explaining the score beyond the badge on the card.
