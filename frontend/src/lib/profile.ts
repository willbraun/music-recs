import type { TasteProfile } from '#lib/api.js'

// Mirror the server's limits so errors show early; the server remains the authority.
export const MAX_ITEMS = 50
export const MAX_ITEM_CHARS = 100
export const MAX_NOTES_CHARS = 1000

export function createEmptyProfile(): TasteProfile {
	return {
		liked_genres: [],
		liked_artists: [],
		disliked_genres: [],
		disliked_artists: [],
		notes: '',
	}
}

export function cloneProfile(profile: TasteProfile): TasteProfile {
	return {
		liked_genres: [...profile.liked_genres],
		liked_artists: [...profile.liked_artists],
		disliked_genres: [...profile.disliked_genres],
		disliked_artists: [...profile.disliked_artists],
		notes: profile.notes,
	}
}

export function hasItem(items: readonly string[], item: string): boolean {
	const key = item.trim().toLowerCase()
	return items.some((existing) => existing.trim().toLowerCase() === key)
}

// Mirrors the server, which turns newlines into single spaces.
export function normalizeNotes(notes: string): string {
	return notes.replace(/\s*[\r\n]+\s*/g, ' ').trim()
}

export function isSameProfile(a: TasteProfile, b: TasteProfile): boolean {
	return (
		a.liked_genres.join('\n') === b.liked_genres.join('\n') &&
		a.liked_artists.join('\n') === b.liked_artists.join('\n') &&
		a.disliked_genres.join('\n') === b.disliked_genres.join('\n') &&
		a.disliked_artists.join('\n') === b.disliked_artists.join('\n') &&
		normalizeNotes(a.notes) === normalizeNotes(b.notes)
	)
}
