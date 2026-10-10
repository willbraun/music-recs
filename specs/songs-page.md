# Songs page

Route `/songs`. Browse every analyzed song in the cache, with filters and pagination.

Related: [frontend.md](frontend.md), [song-card.md](song-card.md), [player.md](player.md), [database.md](database.md).

## Page

- Title "Songs" and a result count (for example "128 songs").
- A filter bar (below), then a responsive grid of [song cards](song-card.md) (about 2 columns on narrow windows up to 6 on wide ones), then pagination controls.
- Default view: **Recommended** songs, newest first.
- Loading: a grid of skeleton cards the same size as real cards. Changing filters keeps the old results visible and dimmed until the new ones arrive, to avoid flicker.
- Empty state: "No songs match these filters." with a "Clear filters" button. When the cache has no songs at all: "No songs yet. Find some on the Home page." with a link home.
- Clicking a card plays it with the page's current songs as the queue ([player.md](player.md#queue)).

## Filters

| Filter        | Control                          | Values                            | Default      |
| ------------- | -------------------------------- | --------------------------------- | ------------ |
| Verdict       | Segmented control or `Select`    | Recommended, Not recommended, All | Recommended  |
| Search        | Text `Input`, debounced (300 ms) | Matches title, artist, or album   | Empty        |
| Taste version | `Select`                         | Any, or a specific taste version  | Any          |
| Sort          | `Select`                         | Newest first, Oldest first        | Newest first |

- A "Clear filters" button appears when any filter differs from the default.
- Changing any filter resets to page 1.
- The Taste version options are the distinct `taste_version` values present in the cache. Songs with a NULL taste version only appear under "Any". The options come from the response (see `taste_versions` below).

State lives in the URL query string so the back button, reload, and links work. Only non-default values are written.

`/songs?recommended=all&q=radio&taste_version=2&sort=oldest&page=3`

The URL is the source of truth: the page reads from it and filter controls update it with `goto(..., { keepFocus: true, replaceState: true })`. Page changes use normal history entries.

## Pagination

- Page size is 24, fixed in the UI.
- shadcn-svelte `Pagination` with previous, next, and page numbers (with ellipsis for long ranges).
- A page past the last one (for example after songs are removed) redirects to the last page. Invalid `page` values are treated as 1.
- Changing page scrolls the content area to the top.

## API

`GET /api/songs` changes from returning every song as a bare list to a paginated response. The legacy `web/` page that reads this endpoint must be updated or retired when this ships, because the response shape changes.

### Query parameters

| Parameter       | Type   | Default  | Description                                                                                           |
| --------------- | ------ | -------- | ----------------------------------------------------------------------------------------------------- |
| `page`          | int    | 1        | 1-based page number, `>= 1`                                                                           |
| `page_size`     | int    | 24       | `1` to `100`                                                                                          |
| `recommended`   | bool   | omitted  | `true` returns only recommended songs, `false` only not recommended, omitted returns all              |
| `q`             | string | omitted  | Case-insensitive substring match on `title`, `artist`, or `album`. Trimmed, 1 to 200 characters.      |
| `taste_version` | int    | omitted  | Exact match on `songs.taste_version`                                                                  |
| `sort`          | enum   | `newest` | `newest` is `analyzed_at DESC, rowid DESC` (same as today). `oldest` is `analyzed_at ASC, rowid ASC`. |

Invalid values return 422 (FastAPI validation). The UI's "Recommended" default sends `recommended=true`; "All" omits the parameter.

### Response

```json
{
	"items": [
		{
			"video_id": "abc123",
			"title": "Everything In Its Right Place",
			"artist": "Radiohead",
			"url": "https://www.youtube.com/watch?v=abc123",
			"description": "Verdict: YES (87% confidence)",
			"analyzed_at": "2026-10-10 14:03:22",
			"taste_version": 1,
			"query": "experimental electronic rock",
			"thumbnail_url": "https://img.youtube.com/vi/abc123/hqdefault.jpg",
			"album_art_url": "https://coverartarchive.org/release-group/<mbid>/front-500",
			"album": "Kid A",
			"musicbrainz_recording_id": "<mbid>",
			"musicbrainz_release_group_id": "<mbid>",
			"recommended": true
		}
	],
	"total": 128,
	"page": 1,
	"page_size": 24,
	"taste_versions": [1, 2]
}
```

- `total` is the count of songs matching the filters, ignoring paging.
- `taste_versions` is the sorted list of distinct non-null taste versions in the whole cache, independent of the filters, so the Select always shows every option.
- `recommended` is still derived on read, as today.
- A page beyond the last returns `items: []` with the correct `total`; the UI handles the redirect.

### Implementation notes

- Filtering, ordering, counting, and paging happen in SQL in [appdb.py](../api/appdb.py) with parameterized queries (never string-built values). `AppDb.list_songs` takes the filters, `limit`, and `offset`, and a second method returns the total.
- Recommended filter: `description LIKE 'Verdict: YES%'`. Stored descriptions always use that fixed format, so this matches `get_verdict` in [recommend.py](../api/recommend.py). Not recommended is the songs with a verdict that is not YES; songs without a verdict are never stored.
- `LIKE` patterns for `q` must escape `%`, `_`, and the escape character.
- No new index is needed at the expected size (thousands of rows). Revisit if the table grows much larger.
