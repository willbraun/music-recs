import type { Song } from '#lib/api.js'
import { buildAppleMusicSearchUrl } from '#lib/links.js'
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('#lib/player.svelte.js', () => ({
	player: { current: null, status: 'idle' },
	playSong: vi.fn(),
	togglePlayback: vi.fn(),
}))

import SongCard from './SongCard.svelte'
const ART = 'https://coverartarchive.org/release-group/rg/front-500'
const THUMB = 'https://img.youtube.com/vi/abc/hqdefault.jpg'

const song: Song = {
	video_id: 'abc',
	title: 'Test Song',
	artist: 'Test Artist',
	url: 'https://www.youtube.com/watch?v=abc',
	recommended: true,
	confidence: 0.87,
	query: null,
}

function getImage(container: HTMLElement): HTMLImageElement | null {
	return container.querySelector('img')
}

afterEach(cleanup)

describe('SongCard YouTube link', () => {
	it('opens the song on YouTube in a new tab', () => {
		render(SongCard, { song })

		const link = screen.getByRole('link', {
			name: 'Open Test Song on YouTube',
		})
		expect(link).toHaveAttribute('href', song.url)
		expect(link).toHaveAttribute('target', '_blank')
		expect(link).toHaveAttribute('rel', 'noopener noreferrer')
	})
})

describe('SongCard Apple Music link', () => {
	it('opens an Apple Music search for the song in a new tab', () => {
		render(SongCard, { song })

		const link = screen.getByRole('link', {
			name: 'Open Test Song on Apple Music',
		})
		expect(link).toHaveAttribute('href', buildAppleMusicSearchUrl(song))
		expect(link).toHaveAttribute('target', '_blank')
		expect(link).toHaveAttribute('rel', 'noopener noreferrer')
	})
})

describe('SongCard artwork', () => {
	it('prefers the album art over the YouTube thumbnail', () => {
		const { container } = render(SongCard, {
			song: { ...song, album_art_url: ART, thumbnail_url: THUMB },
		})

		expect(getImage(container)).toHaveAttribute('src', ART)
	})

	it('uses the YouTube thumbnail when there is no album art', () => {
		const { container } = render(SongCard, {
			song: { ...song, album_art_url: null, thumbnail_url: THUMB },
		})

		expect(getImage(container)).toHaveAttribute('src', THUMB)
	})

	it('falls back to the thumbnail when the album art fails to load', async () => {
		const { container } = render(SongCard, {
			song: { ...song, album_art_url: ART, thumbnail_url: THUMB },
		})

		await fireEvent.error(getImage(container)!)

		expect(getImage(container)).toHaveAttribute('src', THUMB)
	})

	it('shows the placeholder when every image fails or none exists', async () => {
		const { container } = render(SongCard, {
			song: { ...song, album_art_url: ART, thumbnail_url: THUMB },
		})

		await fireEvent.error(getImage(container)!)
		await fireEvent.error(getImage(container)!)

		expect(getImage(container)).toBeNull()
		expect(container.querySelector('svg')).toBeInTheDocument()
	})

	it('shows a skeleton until the image has loaded', async () => {
		const { container } = render(SongCard, {
			song: { ...song, thumbnail_url: THUMB },
		})
		const skeleton = () => container.querySelector('[data-slot="skeleton"]')

		expect(skeleton()).toBeInTheDocument()
		await fireEvent.load(getImage(container)!)

		expect(skeleton()).not.toBeInTheDocument()
		expect(getImage(container)).toHaveClass('opacity-100')
	})

	it('loads lazily unless it is in the first row', () => {
		const lazy = render(SongCard, { song: { ...song, thumbnail_url: THUMB } })
		expect(getImage(lazy.container)).toHaveAttribute('loading', 'lazy')
		cleanup()

		const eager = render(SongCard, {
			song: { ...song, thumbnail_url: THUMB },
			eager: true,
		})
		expect(getImage(eager.container)).toHaveAttribute('loading', 'eager')
	})

	it('shows the album name when present', () => {
		const { getByText } = render(SongCard, {
			song: { ...song, album: 'Kid A' },
		})

		expect(getByText('Kid A')).toBeInTheDocument()
	})
})
