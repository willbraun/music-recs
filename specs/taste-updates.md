# Taste updates

Status: planned, not implemented.

Rated songs should refine the taste. This plan adds a new `taste_versions` row built from the feedback received since the current taste was created. Runs already read the highest `taste_versions.id` ([pipeline.py](../api/pipeline.py)), so a new version applies to the next run with no further wiring.

## Prerequisites

- Something must write `feedback`. Today nothing does ([database.md](database.md#feedback), [frontend.md](frontend.md#non-goals-for-now)). A rating endpoint and UI come first.
- Re-rating a song must reset `feedback.created_at` (an upsert, like `AppDb.add_song`). That column is how new feedback is detected.

## Rating UI

Each [song card](song-card.md) gets a like and a dislike toggle (`aria-pressed`, labeled). Notes are collected only for dislikes.

- **Like:** saves `{rating: 1}` immediately with no note. Clicking the active like clears the rating.
- **Dislike:** saves `{rating: -1}` immediately and opens a popover anchored to the toggle with a one-line field, placeholder "Why? (optional)". Enter or blur saves the note. Escape or clicking away closes it and keeps the rating with no note.
- **Active dislike:** clicking it reopens the popover with the saved note. The popover has a Clear rating button, which is how a dislike is removed.
- **Switching** from dislike to like saves `{rating: 1}` and drops the note. Switching from like to dislike opens the popover.
- The popover moves focus into the field and returns it to the toggle on close.

The rating is saved before the note, so skipping the note never loses the rating. Saving a note re-sends the same rating, which resets `created_at`.

Endpoints:

- `PUT /songs/{video_id}/feedback` with `{rating, note?}` upserts the row.
- `DELETE /songs/{video_id}/feedback` clears it.

The song card needs `rating` and `note` props, and the Songs page can later filter by Liked, Disliked, and Unrated. Update [song-card.md](song-card.md) and [songs-page.md](songs-page.md) when building this.

## What counts as new feedback

Feedback rows with `created_at` later than the current taste version's `created_at`:

```sql
SELECT f.video_id, f.rating, f.note, s.title, s.artist, s.description, s.query
FROM feedback f JOIN songs s USING (video_id)
WHERE f.created_at > (SELECT created_at FROM taste_versions ORDER BY id DESC LIMIT 1)
ORDER BY f.created_at
```

Both timestamps are second-resolution UTC, so a rating saved in the same second as a new version is missed. This is accepted, since the song stays rated and shows up as a signal in the next update only if re-rated. If it proves a problem, add a migration with an explicit cursor on `taste_versions` instead.

## Trigger

- Manual, never automatic. A taste change alters every later recommendation, so the user starts it.
- Requires at least `MIN_FEEDBACK_FOR_UPDATE` new ratings (start at 10) so one or two ratings cannot rewrite the taste. Below that the request is refused with the current count.
- Not allowed while a run is in progress. Both load a local model, and a run reads the taste once at the start.

## Generating the new text

New module `api/taste.py`, following the shape of [queries.py](../api/queries.py): lazy model load, one generation, unload.

1. Build a prompt from the current taste text, the liked songs (title, artist, query), and the disliked songs (same fields plus `note` when present). Liked and disliked are listed separately. Only dislikes carry notes, since the UI collects notes only for them.
2. Ask for a complete replacement taste text that keeps what still holds, adds what the likes show, and adds exclusions only when dislikes show a pattern. A single dislike is not a pattern.
3. Output is the full text, because the Music Flamingo prompt inserts it unchanged ([analyze.py](../api/analyze.py)).

Constraints on the output, checked before saving:

- Non-empty, different from the current text, and under a length cap so the audio prompt stays small.
- Keeps a `My favorite artists are A, B, C.` sentence. [queries.py](../api/queries.py) parses it with `_FAVORITE_ARTISTS` for fallback queries.
- Keeps the exclusions of the current taste unless a rating contradicts them.

If validation fails, retry once, then give up without writing anything and report the error. Never save a partial or invalid taste.

## Storage

No schema change. The existing columns are enough:

| Column       | Value                                                                     |
| ------------ | ------------------------------------------------------------------------- |
| `text`       | The validated new taste                                                   |
| `source`     | `feedback`                                                                |
| `note`       | Short summary such as `3 likes, 9 dislikes since version 2`               |
| `created_at` | Set by the database, which also resets the "new feedback" window to empty |

Add to `AppDb`:

- `list_feedback_since_current_taste()`, the query above.
- `add_taste(text, source, note) -> int`, inserts a row and returns the new id.

Versions stay append-only. Undoing an update is a new version copied from an older one with `source = 'revert'`, so the current taste is still the highest `id` and the "since the last taste" window stays correct.

## API

- `GET /taste` returns the current version (`id`, `text`, `source`, `note`, `created_at`) and `new_feedback_count`, so the UI can show when an update is available.
- `POST /taste/draft` runs the generation steps above and returns the proposed text without writing anything, or an error when there is too little feedback, a run is in progress, or generation fails validation.
- `POST /taste` with `{text, note?}` validates the text (the same checks as generated output) and writes the new version with `source = 'feedback'`. The text may be the draft unchanged or edited by the user.

Request and response shapes should follow the existing endpoints in [api.py](../api/api.py).

## Frontend

- Show the new feedback count and an Update taste button, enabled at the threshold, with a loading state while the model runs.
- Show the draft in an editable text area with Save and Discard. Nothing is stored until Save. Save shows validation errors inline.
- Show a Revert action for the current version when it is not the first.
- The Songs page Taste version filter already lists every version present on songs ([songs-page.md](songs-page.md)), so no change is needed there.

## Docs to update when implemented

- [database.md](database.md): `source` now also takes `feedback` and `revert`, and `note` is written.
- [frontend.md](frontend.md): remove rating from the non-goals once the rating UI exists.

## Tests

- `AppDb`: feedback before the current version is excluded, feedback after it is included, a re-rating moves a song into the window, and `add_taste` returns increasing ids.
- Validation: rejects empty, unchanged, over-length, and missing-favorites output. Accepts a good one.
- Feedback endpoints: `PUT` creates and updates, `DELETE` clears, and a re-rating resets `created_at`.
- Draft endpoint: refuses under the threshold, refuses during a run, and never writes a version. The model call is stubbed.
- Save endpoint: writes one version for valid text and none for invalid text.
- Rating UI: dislike opens the popover and like does not, Escape keeps the rating, and the note saves on Enter.

## Open questions

- Is the 3B Qwen model in `queries.py` good enough to rewrite taste text, or does this need a larger model?
