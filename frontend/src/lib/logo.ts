// Single source of truth for the logo geometry. Imported by MusicRecs.svelte and
// scripts/generate-icons.mjs (which runs it directly in Node, so keep it dependency-free).

// Tight crop around the four tiles.
export const LOGO_VIEWBOX = { x: 6, y: 6, size: 88 }

// Strokes are inset by half their width so every tile spans 40 units.
export const LOGO_STROKE_WIDTH = 6
export const LOGO_OUTLINES = [
	{ x: 9, y: 9, size: 34, radius: 5 },
	{ x: 9, y: 57, size: 34, radius: 5 },
	{ x: 57, y: 57, size: 34, radius: 5 },
]

// Left and right edges of the highlighted tile, which the gradient spans.
export const LOGO_GRADIENT = { x1: 54, x2: 94, from: '#ff6ac9', to: '#ffd95e' }

// Highlighted tile with the sound bars as even-odd holes. Not a mask: masks get
// rasterized (blurry) when the browser zooms.
export const LOGO_TILE_PATH = [
	'M62 6H86A8 8 0 0 1 94 14V38A8 8 0 0 1 86 46H62A8 8 0 0 1 54 38V14A8 8 0 0 1 62 6Z',
	'M59.5 29.5a3.5 3.5 0 0 1 7 0v8.5a3.5 3.5 0 0 1-7 0Z',
	'M70.5 14a3.5 3.5 0 0 1 7 0v24a3.5 3.5 0 0 1-7 0Z',
	'M81.5 21.75a3.5 3.5 0 0 1 7 0v16.25a3.5 3.5 0 0 1-7 0Z',
].join(' ')
