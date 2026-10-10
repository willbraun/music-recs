# Songs page

Route `/songs`. Browse every analyzed song in the cache, with filters and pagination.

Related: [frontend.md](frontend.md), [api.md](api.md), [song-card.md](song-card.md), [player.md](player.md), [database.md](database.md).

## Page

- Title "Songs" and a result count (for example "128 songs").
- A filter bar (below), then a responsive grid of [song cards](song-card.md) (about 2 columns on narrow windows up to 6 on wide ones), then pagination controls.
- Default view: **Recommended** songs, newest first.
- Loading: a grid of skeleton cards the same size as real cards. Changing filters keeps the old results visible and dimmed until the new ones arrive, to avoid flicker.
- Empty state: "No songs match these filters." with a "Clear filters" button. When the cache has no songs at all: "No songs yet. Find some on the Home page." with a link home.
- Clicking a card plays it with the page's current songs as the queue ([player.md](player.md#queue)).

## Filters

| Filter  | Control                          | Values                            | Default      |
| ------- | -------------------------------- | --------------------------------- | ------------ |
| Verdict | Segmented control or `Select`    | Recommended, Not recommended, All | Recommended  |
| Search  | Text `Input`, debounced (300 ms) | Matches title, artist, or album   | Empty        |
| Sort    | `Select`                         | Newest first, Oldest first        | Newest first |

- A "Clear filters" button appears when any filter differs from the default.
- Changing any filter resets to page 1.

State lives in the URL query string so the back button, reload, and links work. Only non-default values are written.

`/songs?recommended=all&q=radio&sort=oldest&page=3`

The URL is the source of truth: the page reads from it and filter controls update it with `goto(..., { keepFocus: true, replaceState: true })`. Page changes use normal history entries.

## Pagination

- Page size is 24, fixed in the UI.
- shadcn-svelte `Pagination` with previous, next, and page numbers (with ellipsis for long ranges).
- A page past the last one (for example after songs are removed) redirects to the last page. Invalid `page` values are treated as 1.
- Changing page scrolls the content area to the top.

## API

The page uses `GET /api/songs`, which returns a paginated response. The parameters and response are in [api.md](api.md#get-apisongs). The UI's "Recommended" default sends `recommended=true`, and "All" omits the parameter. A page beyond the last returns `items: []`, and the UI handles the redirect.

### Implementation notes

- Filtering, ordering, counting, and paging happen in SQL in [appdb.py](../api/appdb.py) with parameterized queries (never string-built values). `AppDb.list_songs` takes the filters, `limit`, and `offset`, and a second method returns the total.
- Recommended filter: `description LIKE 'Verdict: YES%'`. Stored descriptions always use that fixed format, so this matches `get_verdict` in [recommend.py](../api/recommend.py). Not recommended is the songs with a verdict that is not YES; songs without a verdict are never stored.
- `LIKE` patterns for `q` must escape `%`, `_`, and the escape character.
- No new index is needed at the expected size (thousands of rows). Revisit if the table grows much larger.
