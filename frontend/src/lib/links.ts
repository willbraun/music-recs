import type { Song } from '#lib/api.js'

const APPLE_MUSIC_SEARCH_URL = 'https://music.apple.com/us/search'

export function buildAppleMusicSearchUrl(
	song: Pick<Song, 'artist' | 'title'>
): string {
	const term = `${song.artist} ${song.title}`.trim()
	return `${APPLE_MUSIC_SEARCH_URL}?term=${encodeURIComponent(term)}`
}
