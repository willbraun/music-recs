# Frontend

A SvelteKit single-page app (SPA) that replaces the legacy `web/` folder. It talks to the existing Python API in [api.py](../api/api.py) and adds no server-side logic of its own.

Related specs: [home.md](home.md), [taste.md](taste.md), [scoring.md](scoring.md), [api.md](api.md), [song-card.md](song-card.md), [player.md](player.md), [songs-page.md](songs-page.md), [artwork.md](artwork.md), [database.md](database.md).

## Stack

| Concern   | Choice                                                                                                                          |
| --------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Framework | SvelteKit with Svelte 5 runes and TypeScript                                                                                    |
| Rendering | SPA only: `adapter-static` with `fallback: 'index.html'`, and `export const ssr = false` in the root layout                     |
| UI kit    | shadcn-svelte (Button, Input, Badge, Skeleton, Pagination, Select, Sonner, etc.)                                                |
| Styling   | Tailwind CSS, as required by shadcn-svelte                                                                                      |
| Animation | Custom (see [home.md](home.md#energy-orb)). Magic UI targets React, so it is not used unless a maintained Svelte port is found. |
| Tests     | Vitest and Svelte Testing Library for logic modules and components; `svelte-check` for types                                    |

The app lives in `frontend/` at the repo root. The legacy `web/` folder is reference only and is left alone until the SPA replaces it.

## Scaffold

`frontend/` does not exist yet. Create it in this order:

1. `npx sv create frontend` with TypeScript, then `npx sv add tailwindcss vitest` (or the equivalent options at the prompt).
2. Replace the default adapter with `@sveltejs/adapter-static` and set `fallback: 'index.html'` in `svelte.config.js`. Add `export const ssr = false` to `src/routes/+layout.ts`.
3. Run `npx shadcn-svelte@latest init`, then add the components listed above as they are needed.
4. Add `@testing-library/svelte`, `@testing-library/jest-dom`, and `jsdom`. Configure Vitest with the `jsdom` environment and the Svelte plugin so component tests run next to logic tests.
5. Add the `/api` proxy to `vite.config.ts` ([Serving](#serving)).
6. Add `check`, `test`, and `build` scripts, and confirm `npm run check`, `npm test`, and `npm run build` pass on the empty app before adding features.

`frontend/node_modules` and `frontend/build` are git-ignored.

## Serving

- **Development:** `vite dev` with a proxy for `/api` to `http://127.0.0.1:8000`. The SSE endpoint must not be buffered by the proxy.
- **Production:** `vite build` writes static files to `frontend/build`. FastAPI mounts that folder in place of `web/` at `/`, still after the `/api` routes, with `html=True` so unknown paths fall back to `index.html` (client-side routing).
- All API calls use relative URLs (`/api/...`), so no base URL setting is needed.

## Routes

| Route    | Page                                                              |
| -------- | ----------------------------------------------------------------- |
| `/`      | Home: find new music ([home.md](home.md))                         |
| `/songs` | Songs: browse all analyzed songs ([songs-page.md](songs-page.md)) |
| `/taste` | Taste: set up or edit the user's taste ([taste.md](taste.md))     |

No other routes for now. Unknown paths show a simple "Not found" page with a link home.

## Layout

The root layout renders, in this order:

1. A header at the top with the app name and links to Home, Songs, and Taste. The active link is highlighted and has `aria-current="page"`. The header stays visible while the page scrolls. There is no sidebar for now; add one only if more pages need it.
2. The page content, scrollable, with bottom padding equal to the player bar height so nothing is hidden behind it.
3. The persistent player bar ([player.md](player.md)), fixed to the bottom of the window and shared by all routes.
4. A toast area (shadcn-svelte Sonner) for errors.

The layout also owns the three pieces of state that must survive navigation: the **player**, the **current run**, and the **taste** (see below).

**Taste gate:** the layout loads the current taste once on start. While it loads, the page content is hidden. If there is no taste, every route except `/taste` redirects to `/taste` ([taste.md](taste.md#first-run)). The app has nothing to show without a taste, so no other page needs its own check.

## Shared state

State lives in `.svelte.ts` modules using runes, not in stores or the DOM. Each module exposes plain functions with verb names.

| Module             | Holds                                                          | Survives route change |
| ------------------ | -------------------------------------------------------------- | --------------------- |
| `player.svelte.ts` | Current song, queue, play state, position, expanded flag       | Yes                   |
| `run.svelte.ts`    | Current run: phase, status text, count, recommendations, error | Yes                   |
| `taste.svelte.ts`  | Current taste: loading, none, ready, or error                  | Yes                   |

Page-specific state (Songs page filters, page number) lives in the URL, not in a module. See [songs-page.md](songs-page.md).

## API client

A typed `api.ts` module wraps `fetch` and defines the TypeScript types for API payloads. Every endpoint, input, and output is described in [api.md](api.md).

| Function               | Request                                                                                   |
| ---------------------- | ----------------------------------------------------------------------------------------- |
| `startRun(count)`      | `POST /api/runs` with `{ "count": n }`, returns `{ id }`                                  |
| `openRunEvents(id)`    | `EventSource` on `GET /api/runs/{id}/events`                                              |
| `listSongs(params)`    | `GET /api/songs` with filters and paging ([api.md](api.md#get-apisongs))                  |
| `getTaste()`           | `GET /api/taste`, returns the saved taste or `null` ([api.md](api.md#get-apitaste))       |
| `saveTaste(profile)`   | `PUT /api/taste` with `{ profile }`, returns the saved taste                              |
| `rateSong(id, rating)` | _Planned._ `PUT /api/songs/{id}/feedback` ([api.md](api.md#put-apisongsvideo_idfeedback)) |
| `clearRating(id)`      | _Planned._ `DELETE /api/songs/{id}/feedback`                                              |

Rules:

- Non-2xx responses throw an error with the server's `detail` message when present.
- Payload types mirror the API exactly. The `Song` type is defined once and used by every component.
- The client never calls MusicBrainz, Cover Art Archive, or YouTube image URLs for lookups. Artwork is resolved by the backend ([artwork.md](artwork.md)). The browser only loads image URLs it is given.

## Error handling

- A `409` from `startRun` means no taste exists. The app clears its taste state and redirects to `/taste`, with no toast.
- Failed requests and `error` run events show a toast with the message. The run phase also moves to `error` ([home.md](home.md#run-lifecycle)).
- If the API is unreachable, pages show an inline message with a Retry button instead of an empty state.
- Images that fail to load fall back as described in [song-card.md](song-card.md#artwork).

## Theming

- Build one excellent dark theme, but architect it so adding light mode later is inexpensive. That gives you the best balance between design quality and development speed.

## Accessibility and motion

- All interactive elements are reachable by keyboard and have visible focus.
- Icon-only buttons have `aria-label`s.
- Animations respect `prefers-reduced-motion`: the orb becomes a static glow and transitions become instant.
- The app is dark-themed by default, since the orb and artwork suit it. A light theme is not required.

## Non-goals (for now)

- Settings for `query` or `exploration`. Runs use the API defaults (`query` null, `exploration` 50).
- Cancelling a run. The API has no cancel endpoint.
- Packaging as a desktop app. The SPA runs in a browser against the local API; the desktop wrapper is a separate decision.
- Authentication. The API is local only.
