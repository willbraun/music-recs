import type { Song } from '#lib/api.js'

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
