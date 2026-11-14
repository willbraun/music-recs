// Regenerates every Tauri icon from src/lib/logo.ts: `npm run icons`.
import { execFileSync } from 'node:child_process'
import { rmSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import {
	LOGO_GRADIENT,
	LOGO_OUTLINES,
	LOGO_STROKE_WIDTH,
	LOGO_TILE_PATH,
	LOGO_VIEWBOX,
} from '../src/lib/logo.ts'

const root = fileURLToPath(new URL('..', import.meta.url))
const iconsDir = `${root}src-tauri/icons`
const sourcePath = `${root}src-tauri/app-icon.svg`

// Matches the dark theme's --background and --foreground.
const BACKGROUND = '#0a0a0a'
const FOREGROUND = '#fafafa'

// The plate fills the canvas edge to edge; only the rounded corners are transparent.
const CANVAS = 1024
const PLATE = CANVAS
const PLATE_RADIUS = 0
const GLYPH = 640

function buildAppIconSvg() {
	const { x, y, size } = LOGO_VIEWBOX
	const scale = GLYPH / size
	const center = CANVAS / 2
	const margin = (CANVAS - PLATE) / 2
	const outlines = LOGO_OUTLINES.map(
		(o) =>
			`<rect x="${o.x}" y="${o.y}" width="${o.size}" height="${o.size}" rx="${o.radius}"/>`
	).join('')

	return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${CANVAS} ${CANVAS}" width="${CANVAS}" height="${CANVAS}">
<defs><linearGradient id="g" x1="${LOGO_GRADIENT.x1}" y1="0" x2="${LOGO_GRADIENT.x2}" y2="0" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="${LOGO_GRADIENT.from}"/><stop offset="1" stop-color="${LOGO_GRADIENT.to}"/></linearGradient></defs>
<rect x="${margin}" y="${margin}" width="${PLATE}" height="${PLATE}" rx="${PLATE_RADIUS}" fill="${BACKGROUND}"/>
<g transform="translate(${center} ${center}) scale(${scale}) translate(${-(x + size / 2)} ${-(y + size / 2)})">
<g fill="none" stroke="${FOREGROUND}" stroke-width="${LOGO_STROKE_WIDTH}">${outlines}</g>
<path fill="url(#g)" fill-rule="evenodd" d="${LOGO_TILE_PATH}"/>
</g>
</svg>
`
}

writeFileSync(sourcePath, buildAppIconSvg())
execFileSync('npx', ['tauri', 'icon', sourcePath], {
	cwd: root,
	stdio: 'inherit',
})

// `tauri icon` also writes mobile icons and a 64x64 PNG; this is a desktop-only app.
for (const extra of ['android', 'ios', '64x64.png']) {
	rmSync(`${iconsDir}/${extra}`, { recursive: true, force: true })
}
