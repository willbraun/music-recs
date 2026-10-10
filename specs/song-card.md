# Song card

A reusable component that shows one song. It is used in the Home carousel ([home.md](home.md)) and the Songs page grid ([songs-page.md](songs-page.md)).

## Data

Props are a `Song` as returned by `GET /api/songs` or a `scored` event:

| Field             | Used for                                           |
| ----------------- | -------------------------------------------------- |
| `video_id`        | Playing the song, loading-card matching, list keys |
| `title`, `artist` | Text                                               |
| `album`           | Optional subtitle                                  |
| `album_art_url`   | Preferred image                                    |
| `thumbnail_url`   | Fallback image                                     |
| `url`             | "Open on YouTube" link                             |
| `description`     | Parsed for the confidence value                    |
| `recommended`     | Shows a badge on the Songs page when false         |

All new fields are nullable. See [artwork.md](artwork.md).

## Layout

- Square image (1:1) on top, rounded corners, `object-cover`. A 16:9 YouTube thumbnail is center-cropped.
- Below the image: title (one line, ellipsis, full title in a tooltip), artist (one line), and album (one line, muted) if present.
- A confidence badge (for example "87%") in a corner of the image. The value comes from `Verdict: YES (N% confidence)` in `description`; if it cannot be parsed, no badge is shown. The parser is a small tested function, not inline regex in the component.
- On the Songs page, songs with `recommended = false` show a muted "Not recommended" badge.
- Fixed width in the carousel; fluid width in the grid.

## Interaction

- A play button overlays the image on hover and focus. Clicking the image or the button plays the song in the [player](player.md).
- The card whose `video_id` is the player's current song shows an animated equalizer indicator and a highlighted border. A pause icon replaces the play icon while it is playing.
- A secondary "Open on YouTube" icon link (`url`, new tab, `rel="noopener noreferrer"`) in the card's corner.
- The whole card is keyboard focusable through its play button.

## Artwork

Image source order:

1. `album_art_url` if present.
2. `thumbnail_url` if present.
3. A neutral placeholder (music note icon on a dark background).

If an image fails to load (for example Cover Art Archive returns 404), the card moves to the next source in the list and does not retry the failed one. While an image loads, a shadcn-svelte `Skeleton` fills the square, and the image fades in when ready. Images use `loading="lazy"` except in the first visible row.

## Loading variant

Shown on Home between `analyzing` and `scored` ([home.md](home.md#recommendations-carousel)):

- Same size as a normal card so the layout does not shift when it resolves.
- Image: `thumbnail_url`, dimmed, with a centered spinner.
- Text: title and artist from the `analyzing` event.
- No play button, badge, or links.
- Has `aria-busy="true"` and an accessible label such as "Analyzing {title}".
