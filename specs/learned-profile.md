# Learned profile

Status: planned, not implemented.

The user owns the [taste](taste.md). Their ratings are a separate, system-owned input that shapes each run without ever editing the taste. The learned profile is computed from the ratings, rendered as a short text block, and sent to the models next to the taste. It needs no model and is recomputed from `feedback` whenever it is used. The block is saved with each run, so it is always possible to see what feedback produced a song.

Related: [taste.md](taste.md), [api.md](api.md), [database.md](database.md), [song-card.md](song-card.md).

## Why it is separate

- Stated preferences are explicit and stable, and include hard rules such as "never country". Ratings are noisy and per-song. A dislike can mean a bad song or just not now, and rarely means a bad genre.
- Mixing them in one text would let a few ratings quietly override what the user wrote, and the user could no longer tell what they wrote from what was inferred.
- Ratings should still have an effect right away, without an approval step. That is why the taste is never rewritten from them.

So the taste stays hard rules, and the learned profile is soft guidance. The prompt says so, and the code enforces it where it can ([Precedence](#precedence)).

## Rating songs

Each [song card](song-card.md) gets a like and a dislike toggle (`aria-pressed`, labeled). Only one can be active at a time.

- Clicking an inactive toggle saves that rating immediately, replacing the other one if it was active.
- Clicking the active toggle clears the rating.

There is no note or reason field. A rating is only a like or a dislike.

Re-rating a song resets `feedback.created_at`, so the column is when the current rating was saved. The learned profile uses it to break ties between artists.

The endpoints are in [api.md](api.md#songs). Saving a rating is an upsert, like `AppDb.add_song`.

The song card needs a `rating` prop, and the Songs page can later filter by Liked, Disliked, and Unrated. Update [song-card.md](song-card.md) and [songs-page.md](songs-page.md) when building this.

## What the profile contains

Two lists of artists, counted from the user's likes and dislikes: artists the user tends to like and artists they tend to dislike.

Nothing in the profile needs a model. Genres are not counted, because songs have no genre data and genres are not looked up from MusicBrainz for this.

### Shape

`api/learned.py` builds the profile as this object. `render_learned` turns it into text. The profile is internal and is never returned by the API or shown in the UI.

```json
{
	"liked_artists": [
		{ "name": "Flume", "likes": 2, "dislikes": 0 },
		{ "name": "Mac Miller", "likes": 1, "dislikes": 0 }
	],
	"disliked_artists": [{ "name": "Example Band", "likes": 1, "dislikes": 3 }],
	"rating_count": 14
}
```

| Field              | Type                              | Notes                                                                                                                                  |
| ------------------ | --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| `liked_artists`    | list of `{name, likes, dislikes}` | At most `MAX_ARTISTS`, strongest first, after [precedence](#precedence). `name` is as stored on the artist's most recently rated song. |
| `disliked_artists` | list of `{name, likes, dislikes}` | Same rules                                                                                                                             |
| `rating_count`     | integer                           | All rated songs, not only those in the lists                                                                                           |

- Lists are empty when there is nothing to show. The profile is empty when both lists are empty, and then `render_learned` returns nothing and a run sends no learned profile.
- `likes` and `dislikes` are the artist's full counts, not only the ratings that put it in the group.

### Artists

The profile finds artists the user keeps liking or disliking by counting their rated songs. There is no time weighting. Every rating counts until the user changes or clears it on the Songs page, which is the way to correct an old opinion.

For each artist (`songs.artist`, trimmed, compared ignoring case):

1. Count the artist's songs rated like (`likes`) and rated dislike (`dislikes`).
2. The artist is a **liked artist** when `likes` is greater than `dislikes`. One like is enough.
3. The artist is a **disliked artist** when `dislikes` is greater than `likes` and there are at least `MIN_DISLIKES` dislikes. One dislike is never enough, since it may be about that song and not the artist.
4. An artist with equal likes and dislikes, or with a single dislike, is in neither group.
5. Each group is ordered by the gap between the counts (`likes - dislikes` for liked, `dislikes - likes` for disliked), largest first. Ties go to the artist whose rating was saved most recently. Only the first `MAX_ARTISTS` of each group are kept.

Examples:

| Artist | Likes | Dislikes | Result                             |
| ------ | ----- | -------- | ---------------------------------- |
| A      | 2     | 0        | Liked, gap 2                       |
| B      | 1     | 0        | Liked, gap 1                       |
| C      | 1     | 3        | Disliked, gap 2                    |
| D      | 0     | 1        | Neither, one dislike is not enough |
| E      | 1     | 1        | Neither, the counts are equal      |

The numbers are constants in `api/learned.py`:

| Constant            | Value | Meaning                                             |
| ------------------- | ----- | --------------------------------------------------- |
| `MIN_DISLIKES`      | 2     | Dislikes needed before an artist counts as disliked |
| `MAX_ARTISTS`       | 5     | Artists kept in each group                          |
| `LEARNED_MAX_CHARS` | 600   | Length cap of the rendered text                     |

### Precedence

The taste wins. An artist is left out of the profile when it appears in either artist list of the saved taste, ignoring case. An artist the user already likes is redundant, and one they dislike must not be re-added by a rating. This also means ratings cannot override the taste. If the user rates songs by a listed favorite badly, they change the taste themselves.

## Rendering

`render_learned(profile)` in `api/learned.py` returns one paragraph, or nothing when the profile is empty:

```
Learned from my ratings (guidance only, my taste above takes precedence): I liked songs by A, B. I disliked songs by C.
```

Empty sentences are omitted. The text is capped at `LEARNED_MAX_CHARS` so the audio prompt stays small. When over, the artists with the smallest gap are dropped first.

## How it is used

The pipeline ([pipeline.py](../api/pipeline.py)) builds the profile once at the start of a run and uses the same rendered text everywhere. Ratings saved during a run apply to the next one.

- **Queries** ([queries.py](../api/queries.py)):
  - The block follows the taste in the prompt.
  - Learned liked artists join the pool of familiar fallback queries.
  - A generated query that equals a learned disliked artist, ignoring case, is dropped and replaced from that pool. This is a code rule and does not depend on the model.
- **Analysis** ([analyze.py](../api/analyze.py)): the block is added to the text prompt after the taste, before the exploration guidance. The exploration guidance is unchanged.

Learned guidance never overrides the taste in the prompt text. Hard exclusions still come only from the taste.

## Run snapshot

Each run saves what it used, so the feedback behind a song is a lookup, not an inference from dates. Dates are not enough, because `feedback` keeps one row per song and a re-rating or clear erases what it was before.

- `AppDb.add_run(query, count, exploration, taste_text, learned_profile) -> int` inserts a `runs` row and returns the id. The pipeline calls it after rendering the taste and building the learned profile.
- `songs.run_id` is set when a song is added.
- The `started` event gains `run_id`.
- The database stores the rendered text, not the structured data, since the text is what the models received. The taste is stored the same way, so the run holds the exact taste it used even after the user edits it.

Showing "why was this recommended" in the UI is future work. The data is kept so it can be added.

## Storage

Nothing is stored for the learned profile itself. It is recomputed from `feedback` at the start of each run, so it cannot go stale. Runs keep a copy of what they used ([database.md](database.md#runs)).

## API

The learned profile has no endpoint of its own. The rating endpoints are under [Songs](api.md#songs).

## Frontend

Only the rating toggles on the song card, as above. The learned profile is not displayed anywhere.

## Docs to update when implemented

- [database.md](database.md): `feedback` now has a writer.
- [frontend.md](frontend.md): remove rating from the non-goals, and drop the _planned_ marks on the rating calls in the API client.

## Tests

- Artist counting: more likes than dislikes is liked, one dislike is not enough, equal counts are in neither group, artists are matched ignoring case, ties go to the most recent rating, and each group is capped.
- Precedence: artists in the taste's lists are omitted.
- `render_learned`: exact output, omitted sentences, `None` when empty, and the cap dropping the weakest artists first.
- Queries: a generated query equal to a learned disliked artist is replaced from the pool.
- Pipeline: one `runs` row per run with the rendered taste and learned profile, and `run_id` on each added song.
- Feedback endpoints: `PUT` creates and updates, `DELETE` clears, and a re-rating resets `created_at`.
- Rating UI: clicking an inactive toggle saves that rating, clicking the active one clears it, and switching from like to dislike replaces the rating.

## Non-goals

- Changing the taste from ratings. The taste only changes when the user edits it.
- Using a model to summarize ratings. The profile is computed.
- Letting the user edit the learned profile. It is derived.
- Rating notes or reasons. A rating is only a like or a dislike.
- Letting the user turn the learned profile off or clear it. It always applies to runs.
- Displaying the learned profile or exposing it through the API.
- Genres in the learned profile, and MusicBrainz genre lookups to support them.
- Reconstructing past feedback from dates.
