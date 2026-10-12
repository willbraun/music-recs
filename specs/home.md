# Home page

Route `/`. The user asks for new music, watches progress, and sees each recommendation appear as soon as it is analyzed.

Related: [frontend.md](frontend.md), [song-card.md](song-card.md), [player.md](player.md).

## Layout

```
+------------------------------------------------------+
|                    (energy orb)                      |
|                                                      |
|        [ Find new music ]   [ - 3 + ]  songs         |
|                                                      |
|  Recommended for you                                 |
|  [card] [card] [card] [card]                         |
|  [card] [loading card]                               |
+------------------------------------------------------+
```

The orb and controls are the hero. The recommendations grid sits below once a run has produced results.

## Requires a taste

Home is only shown when a taste exists. Without one the layout redirects to `/taste` ([taste.md](taste.md#first-run)), so the orb and controls never render on a fresh database. Home has no setup UI of its own.

## Find new music controls

- A primary shadcn-svelte `Button` labelled "Find new music" is the call to action.
- Next to it is a number `Input` for how many songs to find, with a visible label ("Songs").
  - Integer, min 1, max 50, default 3. These match `RunRequest.count` in [api.py](../api/api.py).
  - Out-of-range or empty input disables the button and shows the allowed range in the field's helper text. The value is never silently clamped on submit.
- While a run is active, the button is disabled and shows "Finding music..." and the input is disabled.
- Pressing Enter in the input starts a run.

## Run lifecycle

The run state lives in `run.svelte.ts` so it survives navigation to `/songs` and back.

| Phase       | Meaning                                           | Entered when                      |
| ----------- | ------------------------------------------------- | --------------------------------- |
| `idle`      | No run yet, or the user has not started one       | App start                         |
| `preparing` | Run requested, no song has finished analyzing yet | CTA clicked                       |
| `streaming` | At least one recommendation has arrived           | First recommended `scored` event  |
| `done`      | Run finished                                      | `done` event                      |
| `error`     | Run failed                                        | `error` event, or request failure |

Flow:

1. CTA click calls `POST /api/runs` with `{ count }`, then opens an `EventSource` on `/api/runs/{id}/events`. The run id is saved in `sessionStorage`. On a page reload, the app reopens the stream for that id (the server replays all events from the start). A 404 clears the saved id and returns to `idle`.
2. The previous run's results are cleared when a new run starts. Earlier recommendations remain available on the Songs page.
3. Runs are serialized by the server. Until `started` arrives, the status text is "Waiting for the model..." because another run may be ahead in the queue.
4. The `EventSource` is closed on `done`, on `error`, and when the app is torn down.
5. If the stream drops, the browser reconnects with `Last-Event-ID`, which the server supports. If the stream cannot reconnect, the phase becomes `error` with "Lost connection to the server".

### Events

Event shapes come from `run` in [pipeline.py](../api/pipeline.py). The status text under the orb follows the latest event.

| Event               | Status text                             | Effect                                                  |
| ------------------- | --------------------------------------- | ------------------------------------------------------- |
| `started`           | "Reading your taste..."                 | Stores `count`                                          |
| `downloading_model` | "Downloading model (first run only)..." | None                                                    |
| `queries`           | "Searching..."                          | None                                                    |
| `fetching`          | "Finding songs..."                      | None                                                    |
| `analyzing`         | "Listening to {title} by {artist}..."   | Adds a loading card for the song at the end of the grid |
| `scored`            | "Found {recommended} of {count}"        | See below                                               |
| `done`              | "Found {recommended} of {count}"        | Phase becomes `done`                                    |
| `error`             | The event's `message`                   | Phase becomes `error`, toast shown                      |

Handling `scored` (matched to its loading card by `video_id`):

- `recommended: true`: the loading card turns into a full [song card](song-card.md) in place. If this is the first recommendation, the phase becomes `streaming`.
- `recommended: false`: the loading card is removed. Not-recommended songs are not shown on Home. They appear on the Songs page with the right filter.

`done` with zero recommendations shows an empty state: "No new recommendations this time. Try again for a fresh batch." The CTA is enabled again.

## Energy orb

A custom, decorative component that shows the state of the run. It is `aria-hidden`; status is also exposed as text in an `aria-live="polite"` region.

Visual: a glowing sphere with an animated, shimmering edge (rotating gradient, soft bloom, and a few orbiting particles or noise-driven edge distortion). Implement with CSS/SVG or a `<canvas>`; no animation library. The exact look is a design decision for implementation, using the `frontend-design` skill.

States and motion:

| Phase       | Orb                                                                                                                              |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `idle`      | Medium size, centered above the CTA, dim with a slow pulse                                                                       |
| `preparing` | Brightens and grows to fill most of the viewport, centered, with an energetic edge animation. Status text sits over or under it. |
| `streaming` | Shrinks and moves to the top of the page as the first recommendation arrives. The grid fades in below it.                        |
| `done`      | Stays small at the top, calm slow pulse                                                                                          |
| `error`     | Small, dimmed with a warning tint                                                                                                |

- The grow, shrink, and move are one animated transition of size and position (about 600-800 ms, eased). Layout must not jump: the grid area reserves its height before the orb moves.
- During `streaming`, each new `analyzing` event gives the orb a brief visible pulse, so progress is felt even between cards.
- With `prefers-reduced-motion`, the orb is a static glow and the size change is instant.
- The orb must not capture pointer events or block the CTA.

## Recommendations grid

- A responsive grid of [song cards](song-card.md). Columns fill the available width (`repeat(auto-fill, minmax(12rem, 1fr))`) and rows wrap, so every recommendation is reachable with normal page scrolling. With a small count the grid looks like a single row.
- New cards are appended at the end in the order songs finish analyzing. The page scroll position is never moved automatically. A "New" indicator is not needed.
- The loading card is the last item. It uses the YouTube thumbnail from `thumbnail_url` (see [artwork.md](artwork.md)), dimmed, with a centered spinner, and shows the title and artist from the `analyzing` event.
- Cards fill their grid cell, and appending never reorders or resizes existing cards.
- The grid is hidden in `idle` and `preparing`, and shown from `streaming` onward (or from `done` for the empty state).

## Playback from Home

Clicking a card's play control starts it in the [player](player.md) with the grid's recommended songs as the queue. Cards appended later are added to the end of that queue.
