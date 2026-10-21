import { describe, expect, it } from 'vitest'
import { buildAppleMusicSearchUrl } from './links.js'

describe('buildAppleMusicSearchUrl', () => {
	it('searches the US storefront for the artist and title', () => {
		expect(
			buildAppleMusicSearchUrl({ artist: 'Radiohead', title: 'Weird Fishes' })
		).toBe('https://music.apple.com/us/search?term=Radiohead%20Weird%20Fishes')
	})

	it('encodes characters that would break the query string', () => {
		const url = new URL(
			buildAppleMusicSearchUrl({
				artist: 'Simon & Garfunkel',
				title: 'Weird Fishes/Arpeggi? #1',
			})
		)

		expect(url.searchParams.get('term')).toBe(
			'Simon & Garfunkel Weird Fishes/Arpeggi? #1'
		)
		expect(url.hash).toBe('')
	})

	it('keeps non-ASCII characters intact after decoding', () => {
		const url = new URL(
			buildAppleMusicSearchUrl({ artist: 'Björk', title: 'Jóga' })
		)

		expect(url.searchParams.get('term')).toBe('Björk Jóga')
	})
})
