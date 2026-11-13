import type { Song } from '#lib/api.js'
import { openUrl } from '@tauri-apps/plugin-opener'

// Search links are built from artist and title only; nothing is looked up or stored.
const APPLE_MUSIC_SEARCH_URL = 'https://music.apple.com/us/search'
const SPOTIFY_SEARCH_URL = 'https://open.spotify.com/search'

export function buildAppleMusicSearchUrl(
	song: Pick<Song, 'artist' | 'title'>
): string {
	const term = `${song.artist} ${song.title}`.trim()
	return `${APPLE_MUSIC_SEARCH_URL}?term=${encodeURIComponent(term)}`
}

export function buildSpotifySearchUrl(
	song: Pick<Song, 'artist' | 'title'>
): string {
	const term = `${song.artist} ${song.title}`.trim()
	return `${SPOTIFY_SEARCH_URL}/${encodeURIComponent(term)}`
}

function isTauri(): boolean {
	return '__TAURI_INTERNALS__' in window
}

// The desktop webview ignores target="_blank" clicks, so external URLs go through the opener plugin.
export async function openExternalUrl(url: string): Promise<void> {
	if (isTauri()) {
		await openUrl(url)
		return
	}
	window.open(url, '_blank', 'noopener,noreferrer')
}

// In the browser, target="_blank" already works, so only the desktop app intercepts clicks.
export function handleExternalLinkClick(event: MouseEvent): void {
	if (event.defaultPrevented || !isTauri()) return
	const anchor = (event.target as Element | null)?.closest?.(
		'a[target="_blank"]'
	)
	if (!(anchor instanceof HTMLAnchorElement)) return
	if (anchor.protocol !== 'http:' && anchor.protocol !== 'https:') return
	event.preventDefault()
	void openExternalUrl(anchor.href)
}
