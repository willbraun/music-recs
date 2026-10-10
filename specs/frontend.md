# Frontend

A SvelteKit single-page app (SPA) that replaces the legacy `web/` folder. It talks to the existing Python API in [api.py](../api/api.py) and adds no server-side logic of its own.

Related specs: [home.md](home.md), [song-card.md](song-card.md), [player.md](player.md), [songs-page.md](songs-page.md), [artwork.md](artwork.md), [database.md](database.md).

## Stack

| Concern   | Choice                                                                                                                          |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Framework | SvelteKit with Svelte 5 runes and TypeScript                                                                                    |
| Rendering | SPA only: `adapter-static` with `fallback: 'index.html'`, and `export const ssr = false` in the root layout                     |
| UI kit    | shadcn-svelte (Button, Input, Badge, Skeleton, Pagination, Select, Sonner, etc.)                                                |
| Styling   | Tailwind CSS, as required by shadcn-svelte                                                                                      |
| Animation | Custom (see [home.md](home.md#energy-orb)). Magic UI targets React, so it is not used unless a maintained Svelte port is found. |
| Tests     | Vitest for logic modules; `svelte-check` for types                                                                              |

The app lives in `frontend/` at the repo root. The legacy `web/` folder is reference only and is left alone until the SPA replaces it.

## Serving

- **Development:** `vite dev` with a proxy for `/api` to `http://127.0.0.1:8000`. The SSE endpoint must not be buffered by the proxy.
- **Production:** `vite build` writes static files to `frontend/build`. FastAPI mounts that folder in place of `web/` at `/`, still after the `/api` routes, with `html=True` so unknown paths fall back to `index.html` (client-side routing).
- All API calls use relative URLs (`/api/...`), so no base URL setting is needed.

## Routes

| Route    | Page                                                              |
| -------- | ----------------------------------------------------------------- |
| `/`      | Home: find new music ([home.md](home.md))                         |
| `/songs` | Songs: browse all analyzed songs ([songs-page.md](songs-page.md)) |

No other routes for now. Unknown paths show a simple "Not found" page with a link home.

## Layout

The root layout renders, in this order:

1. A header at the top with the app name and links to Home and Songs. The active link is highlighted and has `aria-current="page"`. The header stays visible while the page scrolls. There is no sidebar for now; add one only if more pages need it.
2. The page content, scrollable, with bottom padding equal to the player bar height so nothing is hidden behind it.
3. The persistent player bar ([player.md](player.md)), fixed to the bottom of the window and shared by all routes.
4. A toast area (shadcn-svelte Sonner) for errors.

The layout also owns the two pieces of state that must survive navigation: the **player** and the **current run** (see below).

## Shared state

State lives in `.svelte.ts` modules using runes, not in stores or the DOM. Each module exposes plain functions with verb names.

| Module             | Holds                                                          | Survives route change |
| ------------------ | -------------------------------------------------------------- | --------------------- |
| `player.svelte.ts` | Current song, queue, play state, position, expanded flag       | Yes                   |
| `run.svelte.ts`    | Current run: phase, status text, count, recommendations, error | Yes                   |

Page-specific state (Songs page filters, page number) lives in the URL, not in a module. See [songs-page.md](songs-page.md).

## API client

A typed `api.ts` module wraps `fetch` and defines the TypeScript types for API payloads.

| Function            | Request                                                                       |
| ------------------- | ----------------------------------------------------------------------------- |
| `startRun(count)`   | `POST /api/runs` with `{ "count": n }`, returns `{ id }`                      |
| `openRunEvents(id)` | `EventSource` on `GET /api/runs/{id}/events`                                  |
| `listSongs(params)` | `GET /api/songs` with filters and paging ([songs-page.md](songs-page.md#api)) |

Rules:

- Non-2xx responses throw an error with the server's `detail` message when present.
- Payload types mirror the API exactly. The `Song` type is defined once and used by every component.
- The client never calls MusicBrainz, Cover Art Archive, or YouTube image URLs for lookups. Artwork is resolved by the backend ([artwork.md](artwork.md)). The browser only loads image URLs it is given.

## Error handling

- Failed requests and `error` run events show a toast with the message. The run phase also moves to `error` ([home.md](home.md#run-lifecycle)).
- If the API is unreachable, pages show an inline message with a Retry button instead of an empty state.
- Images that fail to load fall back as described in [song-card.md](song-card.md#artwork).

## Accessibility and motion

- All interactive elements are reachable by keyboard and have visible focus.
- Icon-only buttons have `aria-label`s.
- Animations respect `prefers-reduced-motion`: the orb becomes a static glow and transitions become instant.
- The app is dark-themed by default, since the orb and artwork suit it. A light theme is not required.

## Non-goals (for now)

- Settings for `query` or `exploration`. Runs use the API defaults (`query` null, `exploration` 50).
- Rating songs. The `feedback` table has no writer yet.
- Cancelling a run. The API has no cancel endpoint.
- Packaging as a desktop app. The SPA runs in a browser against the local API; the desktop wrapper is a separate decision.
- Authentication. The API is local only.
