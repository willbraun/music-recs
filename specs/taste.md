# Taste

Status: planned, not implemented.

The user describes their taste once, before the first run, and can change it later. The taste is entered as structured fields and saved in the single-row `taste` table. Its genres are the text prior of the [scoring](scoring.md#taste-prior), its liked artists seed the audio-based [artist prior](scoring.md#artist-prior), its liked artists and genres, rendered as one text string, feed query generation, and its disliked artists are skipped before scoring ([scoring.md](scoring.md#pipeline)). This replaces the hardcoded `SEED_TASTE` in [appdb.py](../api/appdb.py).

Related: [database.md](database.md#taste), [frontend.md](frontend.md), [home.md](home.md), [scoring.md](scoring.md).

The taste is user-owned and only changes when the user saves the form. Ratings never change it. They train the [scorer](scoring.md). There is no taste history.

## Why structured fields

- Each genre is embedded as its own phrase for the scoring prior, so genres must be separate items, not a sentence.
- [queries.py](../api/queries.py) parses the `My favorite artists are A, B, C.` sentence for fallback queries. A fixed list keeps it present.

## Fields

| Field              | UI                    | Required | Meaning                                        |
| ------------------ | --------------------- | -------- | ---------------------------------------------- |
| `liked_genres`     | Multi-select combobox | Yes      | Genres the user likes (at least one)           |
| `liked_artists`    | Tag input             | No       | Artists the user likes, for search and scoring |
| `disliked_genres`  | Multi-select combobox | No       | Genres to score lower                          |
| `disliked_artists` | Tag input             | No       | Artists never to recommend                     |
| `notes`            | Textarea              | No       | Free text, see [Notes](#notes)                 |

### Rules

Enforced by the server. The form repeats the cheap ones so errors appear early.

- Items are trimmed. Empty items are dropped.
- Items are deduplicated within a list, ignoring case. The first spelling is kept, in entry order.
- At most 50 items per list and 100 characters per item.
- A genre cannot be in both `liked_genres` and `disliked_genres`, and an artist cannot be in both `liked_artists` and `disliked_artists`, ignoring case.

## Notes

`notes` is optional free text for anything the fields do not capture, such as moods, eras, or instruments. It is a string field of `profile`.

- Trimmed. Empty is allowed. At most 2000 characters, else `422`.
- It is only added to the text for query generation. It does not affect the scoring prior or the disliked-artist filter, since those need structured values.

## Rendered text

The server renders the text for query generation with `render_taste(profile)` in the new `api/taste_profile.py`. It is never stored or returned by the API, and the frontend never renders it, so there is one implementation. Disliked artists are not in it, since they are filtered in code.

```
I like these genres: {liked_genres}. My favorite artists are {liked_artists}. Avoid these genres: {disliked_genres}. Notes: {notes}
```

- Lists are joined with `, `. A sentence whose list is empty, or whose `notes` is empty, is omitted. The remaining sentences are joined with one space. `notes` is inserted as written, with no added period.
- The pipeline passes `liked_artists` straight to `generate_queries` for fallback queries, so [queries.py](../api/queries.py) no longer needs `_FAVORITE_ARTISTS` to parse the text. Names that contain commas or `. ` work.

Example:

```
I like these genres: Electronic, Indie rock. My favorite artists are Tame Impala, Flume. Avoid these genres: Country. Notes: I like long instrumental builds.
```

## Storage

The `taste` table has one row ([database.md](database.md#taste)). Saving overwrites it.

| Column       | Value                                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| `profile`    | The normalized fields as JSON, `{liked_genres, liked_artists, disliked_genres, disliked_artists, notes}` |
| `updated_at` | The time of the save                                                                                     |

Saving without changes is allowed and only refreshes `updated_at`. The form disables Save when nothing changed, so this only happens through the API.

## API

The endpoints and their shapes are in [api.md](api.md#taste).

- Validation failures return `422` with `detail` as one readable message (the first failure), so the client rule "throw the server's `detail`" works unchanged. A failed save writes nothing.
- Saving while a run is active is allowed. A run reads the taste once at its start, so the active run keeps what it read. Queued runs that have not started use the new one.
- `POST /api/runs` returns `409` with `detail: "Set your taste first"` when no taste has been saved. The CLI ([main.py](../api/main.py)) prints "No taste set. Open the app to set one." and exits.

## First run

A fresh database has no taste. The root layout loads the current taste once. While it loads, the page content is hidden to avoid a flash. When the result is `null` and the route is not `/taste`, the layout redirects to `/taste`. Every other route requires a taste. After saving, the app goes to `/`.

## Taste page

Route `/taste`, linked in the header as "Taste". The same page is the setup screen and the edit screen.

```
+------------------------------------------------------+
|  Your taste                                          |
|  (setup only) Tell us what you like to get started.  |
|                                                      |
|  I like                                              |
|    Genres   [ multi-select combobox        v ]       |
|             (Electronic x) (Indie rock x)            |
|    Artists  [ type a name, press Enter       ]       |
|             (Tame Impala x) (Flume x)                |
|                                                      |
|  I don't like                                        |
|    Genres   [ multi-select combobox        v ]       |
|    Artists  [ type a name, press Enter       ]       |
|                                                      |
|  Notes (optional)                                    |
|    [ free text                               ]       |
|    [                                         ]       |
|                                                      |
|  [ Save taste ]                                      |
+------------------------------------------------------+
```

### Genre combobox

- shadcn-svelte Combobox with multiple selection. The popover has a search box and a scrollable list. Selected genres show as removable badges under the field.
- Options come from a hardcoded list in `frontend/src/lib/genres.ts`, shared by the liked and disliked comboboxes. It is not fetched from MusicBrainz or any other service. Initial list: Alternative, Ambient, Bluegrass, Blues, Children's, Christian, Classic rock, Classical, Country, Dance, Disco, Drum and bass, Dubstep, Electronic, Emo, Folk, Funk, Gospel, Grunge, Hard rock, Heavy metal, Hip hop, House, Indie pop, Indie rock, Jazz, K-pop, Latin, Lo-fi, Melodic metal, Metal, New wave, Pop, Post-punk, Psychedelic, Punk, R&B, Reggae, Rock, Shoegaze, Singer-songwriter, Soul, Soundtrack, Synthpop, Techno, Trance, Trap, World.
- Typing text that matches no option offers "Add {text}", so any genre can be entered. The server does not check genres against the list.
- A genre selected in one field is disabled in the other, with the hint "In your likes" or "In your dislikes".

### Artist tag input

- A small `TagInput.svelte` built from `Badge` and `Input`, since shadcn-svelte has no tag input.
- Enter adds the typed name as a chip. Commas are not separators, because names can contain them. Pasted text with newlines becomes one chip per line.
- Backspace in the empty field removes the last chip. Each chip has a remove button labeled "Remove {name}".
- Adding a name already in the list, ignoring case, does nothing. Adding a name that is in the opposite list shows an inline message ("Already in your dislikes" or "Already in your likes") and does not add it.
- The field has a visible label. Chips are a list, and adds and removals are announced through an `aria-live="polite"` region.

### Notes field

- A labeled multi-line `Textarea` below the other fields, with the 2000-character limit shown as a counter. It is a plain controlled field with no formatting.

### Saving

- Save is disabled until there is at least one liked genre and something changed since the saved taste, including `notes`. While saving it shows a loading state.
- A `422` shows its message inline above the button. Other failures show a toast.
- On success, setup navigates to `/` with a "Taste saved" toast. Editing stays on the page and shows the toast.
- There is no unsaved-changes prompt.

## States

- **Loading:** skeleton form.
- **Load error:** inline message with a Retry button.
- **Setup:** no taste saved. The intro line is shown, and the layout keeps the user on this page.
- **Edit:** the form is filled from the saved profile.

## Tests

- `TasteProfile` and `render_taste`: normalization, deduplication, each limit, the liked-and-disliked conflicts for genres and artists, no liked genre rejected, omitted sentences, and the exact output. Notes are trimmed, an over-long note is rejected, and empty notes omit the sentence.
- `AppDb`: `get_current_taste` returns `None` when empty, and saving twice leaves one row with the second profile.
- API: `GET` returns `null` when empty, `PUT` writes for valid input and nothing for invalid input, and `POST /api/runs` returns `409` without a taste and `202` after saving one.
- Migrations: a fresh database ends at the schema in [database.md](database.md) with an empty `taste` table.
- Frontend: the tag input adds on Enter, removes on Backspace, and rejects duplicates and cross-list names. The combobox disables cross-list genres and allows custom entries. Save stays disabled without a liked genre and with no changes, and editing only the notes enables it. The layout redirects to `/taste` when the taste is `null`.

## Non-goals

- Artist autocomplete from YouTube Music or MusicBrainz.
- Keeping a history of earlier tastes.
- Validating genres or artist names against a catalog.
