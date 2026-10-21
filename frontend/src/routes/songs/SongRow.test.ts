import type { Song } from '#lib/api.js'
import { buildAppleMusicSearchUrl } from '#lib/links.js'
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { playerMock } = vi.hoisted(() => ({
	playerMock: { current: null as { video_id: string } | null },
}))

vi.mock('#lib/player.svelte.js', () => ({ player: playerMock }))

import SongRow from './SongRow.svelte'

const ART = 'https://coverartarchive.org/release-group/rg/front-500'
const THUMB = 'https://img.youtube.com/vi/abc/hqdefault.jpg'

const song: Song = {
	video_id: 'abc',
	title: 'Test Song',
	artist: 'Test Artist',
	album: 'Test Album',
	url: 'https://www.youtube.com/watch?v=abc',
	recommended: true,
	confidence: 0.87,
	query: null,
}

function getImage(container: HTMLElement): HTMLImageElement | null {
	return container.querySelector('img')
}

function getPlayButton() {
	return screen.getByRole('button', { name: 'Play Test Song by Test Artist' })
}

beforeEach(() => {
	playerMock.current = null
})

afterEach(cleanup)

describe('SongRow', () => {
	it('shows the title, artist and album', () => {
		render(SongRow, { song, onplay: vi.fn() })

		expect(screen.getByTitle('Test Song')).toHaveTextContent('Test Song')
		expect(screen.getAllByText('Test Artist').length).toBeGreaterThan(0)
		expect(screen.getByText('Test Album')).toBeInTheDocument()
	})

	it('leaves the album empty when there is none', () => {
		render(SongRow, { song: { ...song, album: null }, onplay: vi.fn() })

		expect(screen.queryByText('Test Album')).toBeNull()
	})

	it('plays the song when the row is clicked', async () => {
		const onplay = vi.fn()
		render(SongRow, { song, onplay })

		await userEvent.click(getPlayButton())

		expect(onplay).toHaveBeenCalledExactlyOnceWith(song)
	})

	it('does not play the song when the menu is opened', async () => {
		const onplay = vi.fn()
		render(SongRow, { song, onplay })

		await userEvent.click(
			screen.getByRole('button', { name: 'More options for Test Song' })
		)

		expect(onplay).not.toHaveBeenCalled()
	})

	describe('match score', () => {
		it('shows the confidence for a recommended song', () => {
			render(SongRow, { song, onplay: vi.fn() })

			expect(screen.getByTitle('Recommended')).toHaveTextContent('87%')
			expect(screen.getByTitle('Recommended')).toHaveTextContent(
				', recommended'
			)
		})

		it('flips the confidence for a song that is not recommended', () => {
			render(SongRow, {
				song: { ...song, recommended: false, confidence: 0.64 },
				onplay: vi.fn(),
			})

			const score = screen.getByTitle('Not recommended')
			expect(score).toHaveTextContent('36%')
			expect(score).toHaveTextContent(', not recommended')
		})
	})

	describe('current song', () => {
		it('marks the row that is playing', () => {
			playerMock.current = { video_id: song.video_id }
			render(SongRow, { song, onplay: vi.fn() })

			expect(getPlayButton()).toHaveAttribute('aria-current', 'true')
		})

		it('does not mark a row for another song', () => {
			playerMock.current = { video_id: 'other' }
			render(SongRow, { song, onplay: vi.fn() })

			expect(getPlayButton()).not.toHaveAttribute('aria-current')
		})
	})

	describe('external links', () => {
		it('offers YouTube and Apple Music in new tabs', async () => {
			render(SongRow, { song, onplay: vi.fn() })

			await userEvent.click(
				screen.getByRole('button', { name: 'More options for Test Song' })
			)

			// jsdom never positions the popover, so it stays visibility:hidden and has no accessible name.
			const youtube = (await screen.findByText('YouTube')).closest(
				'[role="menuitem"]'
			)
			const appleMusic = screen
				.getByText('Apple Music')
				.closest('[role="menuitem"]')
			expect(youtube).toHaveAttribute('href', song.url)
			expect(appleMusic).toHaveAttribute('href', buildAppleMusicSearchUrl(song))
			for (const link of [youtube, appleMusic]) {
				expect(link).toHaveAttribute('target', '_blank')
				expect(link).toHaveAttribute('rel', 'noopener noreferrer')
			}
		})
	})

	describe('artwork', () => {
		it('prefers the album art over the YouTube thumbnail', () => {
			const { container } = render(SongRow, {
				song: { ...song, album_art_url: ART, thumbnail_url: THUMB },
				onplay: vi.fn(),
			})

			expect(getImage(container)).toHaveAttribute('src', ART)
		})

		it('uses the thumbnail when there is no album art', () => {
			const { container } = render(SongRow, {
				song: { ...song, album_art_url: null, thumbnail_url: THUMB },
				onplay: vi.fn(),
			})

			expect(getImage(container)).toHaveAttribute('src', THUMB)
		})

		it('falls back to the thumbnail when the album art fails to load', async () => {
			const { container } = render(SongRow, {
				song: { ...song, album_art_url: ART, thumbnail_url: THUMB },
				onplay: vi.fn(),
			})

			await fireEvent.error(getImage(container)!)

			expect(getImage(container)).toHaveAttribute('src', THUMB)
		})

		it('shows the placeholder icon when there is no image or all fail', async () => {
			const none = render(SongRow, { song, onplay: vi.fn() })
			expect(getImage(none.container)).toBeNull()
			expect(none.container.querySelector('svg.lucide-music')).not.toBeNull()
			cleanup()

			const { container } = render(SongRow, {
				song: { ...song, thumbnail_url: THUMB },
				onplay: vi.fn(),
			})
			await fireEvent.error(getImage(container)!)

			expect(getImage(container)).toBeNull()
			expect(container.querySelector('svg.lucide-music')).not.toBeNull()
		})

		it('fades the image in once it has loaded', async () => {
			const { container } = render(SongRow, {
				song: { ...song, thumbnail_url: THUMB },
				onplay: vi.fn(),
			})
			expect(getImage(container)).toHaveClass('opacity-0')

			await fireEvent.load(getImage(container)!)

			expect(getImage(container)).toHaveClass('opacity-100')
		})
	})
})
