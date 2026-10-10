# Player

A persistent bar at the bottom of every page that plays the YouTube video for a song. It is mounted once in the root layout ([frontend.md](frontend.md#layout)) so playback continues while the user navigates.

## Playback technology

- Uses the YouTube IFrame Player API (`https://www.youtube.com/iframe_api`). The script is loaded once, lazily, the first time a song is played.
- One `YT.Player` instance exists for the whole app. It is created in the layout and is never destroyed or re-parented, because moving an iframe in the DOM reloads it and stops playback.
- Our own controls call the player API: `playVideo`, `pauseVideo`, `seekTo`, `getCurrentTime`, `getDuration`, `setVolume`, `mute`, `unMute`, `loadVideoById`. The embedded video's own controls are disabled (`controls: 0`) so there is one control surface.
- State changes come from the `onStateChange` and `onError` callbacks. Current time is polled with a timer (about 4 times per second) only while playing and while the bar is visible.
- Player parameters: `playsinline: 1`, `rel: 0`, `modestbranding: 1`, `origin` set to the app's origin.

## State

Held in `player.svelte.ts`:

| Field      | Description                                                 |
| ---------- | ----------------------------------------------------------- |
| `current`  | The song being played, or null                              |
| `queue`    | Ordered list of songs, and the index of `current` within it |
| `status`   | `idle`, `loading`, `playing`, `paused`, `error`             |
| `position` | Seconds played                                              |
| `duration` | Seconds total                                               |
| `volume`   | 0-100, saved to `localStorage`, default 80                  |
| `muted`    | Boolean, saved to `localStorage`                            |
| `expanded` | Whether the bar is expanded                                 |

Exposed functions: `playSong(song, queue)`, `togglePlayback()`, `playNext()`, `playPrevious()`, `seekTo(seconds)`, `setVolume(n)`, `toggleMute()`, `toggleExpanded()`, `appendToQueue(songs)`.

## Queue

- Playing a card sets the queue to the list that card was shown in and the index to that card:
  - Home: the recommendations in the carousel. New recommendations are appended with `appendToQueue`.
  - Songs page: the songs on the current page, after filters are applied.
- The queue is a snapshot. Changing filters or pages on the Songs page does not change the playing queue.
- When a video ends, the next song plays automatically. At the end of the queue, playback stops and the bar stays on the last song with status `paused`.
- Previous: if more than 3 seconds have played, restart the current song; otherwise go to the previous song. At the start of the queue, restart the current song.
- The queue is not persisted across app restarts.

## Collapsed bar

Fixed to the bottom, full width, about 72 px tall. Hidden until the first song is played, then it slides in.

```
[video 16:9] Title - Artist     [prev][play/pause][next]   0:42 ----o---- 3:10   [vol]  [expand]
```

- A small live video (about 96 x 54 px) at the left. This is the real iframe, sized with CSS.
- Title and artist, one line each, ellipsis. The title links to nothing; an "Open on YouTube" icon link is in the controls.
- Previous, play/pause, next buttons (shadcn-svelte `Button`, `variant="ghost"`, icon size).
- A seek slider (shadcn-svelte `Slider`) with elapsed and total time. Dragging seeks on release.
- A volume control: mute toggle with a slider that appears on hover or focus.
- An expand button.
- While `loading`, play/pause shows a spinner. Controls other than expand are disabled when `current` is null.

## Expanded view

- Toggled by the expand button, the collapse button, or the Escape key when the bar has focus.
- The bar grows upward into a panel that shows the video large, 16:9, capped to the available height, with the same controls under it and the title and artist above.
- The panel sits over the page content (not pushing it) with a dimmed backdrop on the page. Clicking the backdrop collapses it.
- The same iframe element is resized between the two layouts (CSS transition on size and position). It is not re-created.
- The expanded flag is not persisted.

## Errors

`onError` codes from the IFrame API:

| Code     | Meaning                         | Behavior                                                                                     |
| -------- | ------------------------------- | -------------------------------------------------------------------------------------------- |
| 2        | Invalid video id                | Toast "This video can't be played", skip to the next song                                    |
| 5        | HTML5 player error              | Same                                                                                         |
| 100      | Video removed or private        | Same                                                                                         |
| 101, 150 | Embedding disabled by the owner | Toast "This video can't be embedded" with an "Open on YouTube" action, skip to the next song |

If there is no next song, status becomes `error` and the bar shows the message with the "Open on YouTube" link.

## Media keys

Register the Media Session API (`navigator.mediaSession`) with title, artist, artwork (`album_art_url` or `thumbnail_url`), and handlers for play, pause, previous track, and next track, so hardware keys and OS controls work.

## Accessibility

- Controls are real buttons with `aria-label`s ("Play", "Pause", "Next song", "Previous song", "Expand player", "Mute").
- The seek slider has an `aria-valuetext` such as "0:42 of 3:10".
- The current song is announced in an `aria-live="polite"` region when it changes.
- The bar has `role="region"` and `aria-label="Music player"`.
