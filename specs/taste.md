# Taste

Status: planned, not implemented.

The user describes their taste once, before the first run, and can change it later. The taste is entered as structured fields and saved in the single-row `taste` table. When a run starts, the server renders the fields into one text string and sends it to the models. This replaces the hardcoded `SEED_TASTE` in [appdb.py](../api/appdb.py).

Related: [database.md](database.md#taste), [frontend.md](frontend.md), [home.md](home.md), [learned-profile.md](learned-profile.md).

The taste is user-owned and only changes when the user saves the form. Ratings never change it. They feed a separate [learned profile](learned-profile.md) that is sent to the models next to the taste. There is no taste history: each run saves the text it used ([database.md](database.md#runs)).

## Why structured fields

- Exclusions are easy to forget in one free-text box. Separate "I don't like" fields make them explicit, and the prompts treat exclusions as hard NOs ([analyze.py](../api/analyze.py)).
- [queries.py](../api/queries.py) parses the `My favorite artists are A, B, C.` sentence for fallback queries. A fixed template keeps it present.
- A deterministic template gives every version the same prompt shape.
- A notes field still carries what the lists cannot, such as era, mood, language, or lyrics.

## Fields

| Field              | UI                    | Required       | Meaning                     |
| ------------------ | --------------------- | -------------- | --------------------------- |
| `liked_genres`     | Multi-select combobox | One of the two | Genres the user likes       |
| `liked_artists`    | Tag input             | One of the two | Artists the user likes      |
| `disliked_genres`  | Multi-select combobox | No             | Genres never to recommend   |
| `disliked_artists` | Tag input             | No             | Artists never to recommend  |
| `notes`            | Textarea              | No             | Anything else, as free text |

"One of the two" means at least one liked genre or liked artist.

### Rules

Enforced by the server. The form repeats the cheap ones so errors appear early.

- Items are trimmed. Empty items are dropped.
- Items are deduplicated within a list, ignoring case. The first spelling is kept, in entry order.
- At most 50 items per list and 100 characters per item.
- Notes are at most 1000 characters. Newlines in notes become single spaces, so the text stays one paragraph.
- An item cannot be in both a liked and a disliked list of the same kind, ignoring case.
- The rendered text is at most 2000 characters, so the audio prompt stays small. The learned profile has its own, smaller cap ([learned-profile.md](learned-profile.md#rendering)).

## Rendered text

The server renders the text with `render_taste(profile)` in the new `api/taste_profile.py`. The frontend never renders it, so there is one implementation.

```
I like these genres: {liked_genres}. My favorite artists are {liked_artists}. Never recommend these genres: {disliked_genres}. Never recommend these artists: {disliked_artists}. Notes: {notes}
```

- Lists are joined with `, `. A sentence whose list is empty is omitted, and so is the notes sentence when notes are empty. The remaining sentences are joined with one space.
- `My favorite artists are` keeps its exact wording, so the text reads the same as before.
- The pipeline passes `liked_artists` straight to `generate_queries` for fallback queries, so [queries.py](../api/queries.py) no longer needs `_FAVORITE_ARTISTS` to parse the text. Names that contain commas or `. ` work.

Example:

```
I like these genres: Electronic, Indie rock. My favorite artists are Tame Impala, Flume. Never recommend these genres: Country. Notes: If songs have lyrics, they should be in English.
```

## Storage

The `taste` table has one row ([database.md](database.md#taste)). Saving overwrites it.

| Column       | Value                                                                                                    |
| ------------ | -------------------------------------------------------------------------------------------------------- |
| `profile`    | The normalized fields as JSON, `{liked_genres, liked_artists, disliked_genres, disliked_artists, notes}` |
| `updated_at` | The time of the save                                                                                     |

Only the fields are stored. The text for the models is rendered from them with `render_taste` at the start of each run, so the two can never disagree. The rendered text is also returned by `GET /api/taste` for display. Each run saves the text it used in `runs.taste_text`.

Saving without changes is allowed and only refreshes `updated_at`. The form disables Save when nothing changed, so this only happens through the API.

## API

The endpoints and their shapes are in [api.md](api.md#taste).

- `GET /api/taste` returns the taste, or `null` when none has been saved. `text` is rendered from `profile` on every read.
- `PUT /api/taste` validates, renders, and overwrites the taste.

A taste is `{profile, text, updated_at}`. `text` is rendered from `profile` on every read.

- Validation failures return `422` with `detail` as one readable message (the first failure), so the client rule "throw the server's `detail`" works unchanged. A failed save writes nothing.
- Saving while a run is active is allowed. A run reads the taste once at its start, so the active run keeps what it read. Queued runs that have not started use the new one.
- `POST /api/runs` returns `409` with `detail: "Set your taste first"` when no taste has been saved. The CLI ([main.py](../api/main.py)) prints "No taste set. Open the app to set one." and exits.

## First run

A fresh database has no taste. The root layout loads the current taste once. While it loads, the page content is hidden to avoid a flash. When the result is `null` and the route is not `/taste`, the layout redirects to `/taste`. Every other route requires a taste. After saving, the app goes to `/`.

An existing database has its old taste removed when it is upgraded ([database.md](database.md#moving-an-existing-database-to-this-schema)), so it is redirected like a fresh one and the user enters their taste again.

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
|  Anything else                                       |
|  [ textarea                                    ]     |
|                                            0/1000    |
|                                                      |
|  [ Save taste ]                                      |
|                                                      |
|  What the model sees (read-only text)                |
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
- Adding a name already in the list, ignoring case, does nothing. Adding a name that is in the opposite list shows an inline message ("Already in your dislikes") and does not add it.
- The field has a visible label. Chips are a list, and adds and removals are announced through an `aria-live="polite"` region.

### Notes

A textarea with the placeholder "Era, mood, language, anything else", a character counter, and a limit of 1000.

### Saving

- Save is disabled until there is at least one liked genre or liked artist and something changed since the saved taste. While saving it shows a loading state.
- A `422` shows its message inline above the button. Other failures show a toast.
- On success, setup navigates to `/` with a "Taste saved" toast. Editing stays on the page, shows the toast, and refreshes "What the model sees".
- There is no unsaved-changes prompt.

### What the model sees

Below the form, the current `text` in a read-only block. It makes the rendering visible without a second implementation.

## States

- **Loading:** skeleton form.
- **Load error:** inline message with a Retry button.
- **Setup:** no taste saved. The intro line is shown, and the layout keeps the user on this page.
- **Edit:** the form is filled from the saved profile.

## Tests

- `TasteProfile` and `render_taste`: normalization, deduplication, each limit, the liked-and-disliked conflict, empty likes rejected, omitted sentences, and the exact output.
- `AppDb`: `get_current_taste` returns `None` when empty, saving twice leaves one row with the second profile, and `add_run` stores the rendered taste text.
- API: `GET` returns `null` when empty, `PUT` writes for valid input and nothing for invalid input, and `POST /api/runs` returns `409` without a taste and `202` after saving one.
- Upgrading an existing database: a database with a seed taste and songs ends with an empty `taste` table and all songs kept without `taste_version`. Rated songs and their feedback survive the rebuild. A fresh database ends at the same schema.
- Frontend: the tag input adds on Enter, removes on Backspace, and rejects duplicates and cross-list items. The combobox disables cross-list genres and allows custom entries. Save stays disabled without a like and with no changes. The layout redirects to `/taste` when the taste is `null`.

## Non-goals

- Artist autocomplete from YouTube Music or MusicBrainz.
- Keeping a history of earlier tastes. Each run saves the text it used.
- Validating genres or artist names against a catalog.

## Notes for the future

- If queries by item are ever needed (for example, which songs came from a liked artist), move `profile` into a `taste_items` table, backfilled from the JSON.
