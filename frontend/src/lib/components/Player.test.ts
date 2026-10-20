import type { Song } from '#lib/api.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { playSongMock, togglePlaybackMock, toggleExpandedMock } = vi.hoisted(
	() => ({
		playSongMock: vi.fn(),
		togglePlaybackMock: vi.fn(),
		toggleExpandedMock: vi.fn(),
	})
)

vi.mock('#lib/player.svelte.js', () => ({
	player: {
		current: null,
		queue: [],
		index: -1,
		status: 'idle',
		position: 0,
		duration: 0,
		volume: 80,
		muted: false,
		expanded: false,
		error: null,
	},
	attachPlayerHost: vi.fn(),
	detachPlayerHost: vi.fn(),
	playSong: playSongMock,
	togglePlayback: togglePlaybackMock,
	toggleExpanded: toggleExpandedMock,
	toggleMute: vi.fn(),
	setVolume: vi.fn(),
	seekTo: vi.fn(),
	playNext: vi.fn(),
	playPrevious: vi.fn(),
}))

import { player } from '#lib/player.svelte.js'
import Player from './Player.svelte'
import SongCard from './SongCard.svelte'

const song: Song = {
	video_id: 'abc',
	title: 'Test Song',
	artist: 'Test Artist',
	url: 'https://www.youtube.com/watch?v=abc',
	recommended: true,
	confidence: 0.87,
	query: null,
}

beforeEach(() => {
	Object.assign(player, {
		current: null,
		queue: [],
		index: -1,
		status: 'idle',
		position: 0,
		duration: 0,
		expanded: false,
		error: null,
	})
	playSongMock.mockReset()
	togglePlaybackMock.mockReset()
	toggleExpandedMock.mockReset()
})

afterEach(cleanup)

describe('song card playback', () => {
	it('plays the song with its queue when the play button is clicked', async () => {
		render(SongCard, { song, queue: [song], origin: 'run' })

		await userEvent.click(
			screen.getByRole('button', { name: 'Play Test Song' })
		)

		expect(playSongMock).toHaveBeenCalledWith(song, [song], 'run')
	})

	it('toggles playback instead when the song is already current', async () => {
		Object.assign(player, { current: song, status: 'playing' })
		render(SongCard, { song })

		await userEvent.click(
			screen.getByRole('button', { name: 'Pause Test Song' })
		)

		expect(togglePlaybackMock).toHaveBeenCalled()
		expect(playSongMock).not.toHaveBeenCalled()
	})
})

describe('player bar', () => {
	it('is a labelled region with the transport controls', () => {
		Object.assign(player, {
			current: song,
			queue: [song],
			index: 0,
			status: 'paused',
			duration: 190,
		})
		render(Player)

		expect(
			screen.getByRole('region', { name: 'Music player' })
		).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Play' })).toBeEnabled()
		expect(screen.getByRole('button', { name: 'Next song' })).toBeDisabled()
		expect(
			screen.getByRole('button', { name: 'Previous song' })
		).toBeInTheDocument()
		expect(
			screen.getByRole('link', { name: 'Open on YouTube' })
		).toHaveAttribute('href', song.url)
	})

	it('toggles playback and expansion from the controls', async () => {
		Object.assign(player, { current: song, queue: [song], index: 0 })
		player.status = 'paused'
		render(Player)

		await userEvent.click(screen.getByRole('button', { name: 'Play' }))
		await userEvent.click(screen.getByRole('button', { name: 'Expand player' }))

		expect(togglePlaybackMock).toHaveBeenCalled()
		expect(toggleExpandedMock).toHaveBeenCalled()
	})

	it('shows the current position on the seek slider in whole seconds', () => {
		Object.assign(player, {
			current: song,
			queue: [song],
			index: 0,
			status: 'playing',
			position: 42.6,
			duration: 190.4,
		})
		render(Player)

		expect(screen.getByText('0:42')).toBeInTheDocument()
		expect(screen.getByText('3:10')).toBeInTheDocument()
		const [seek] = screen.getAllByRole('slider', { hidden: true })
		expect(seek).toHaveAttribute('aria-valuenow', '42')
		expect(seek).toHaveAttribute('aria-valuetext', '0:42 of 3:10')
	})

	it('hides the video while a new song loads but not while rebuffering', () => {
		Object.assign(player, {
			current: song,
			queue: [song],
			index: 0,
			status: 'loading',
			duration: 0,
		})
		render(Player)
		expect(screen.getByTestId('player-video').className).toContain(
			'[&>iframe]:invisible'
		)

		player.duration = 190
		cleanup()
		render(Player)
		expect(screen.getByTestId('player-video').className).not.toContain(
			'[&>iframe]:invisible'
		)
	})

	it('shows square collapsed artwork for album art, thumbnails and the placeholder', () => {
		Object.assign(player, {
			current: { ...song, album_art_url: 'https://example.com/album.jpg' },
			queue: [song],
			index: 0,
			status: 'playing',
		})
		render(Player)
		expect(screen.getByTestId('player-video').style.width).toBe('54px')

		Object.assign(player, {
			current: { ...song, thumbnail_url: 'https://example.com/thumb.jpg' },
		})
		cleanup()
		render(Player)
		expect(screen.getByTestId('player-video').style.width).toBe('54px')

		Object.assign(player, { current: song })
		cleanup()
		render(Player)
		expect(screen.getByTestId('player-video').style.width).toBe('54px')
	})

	it('shows the error message for the current song', () => {
		Object.assign(player, {
			current: song,
			queue: [song],
			index: 0,
			status: 'error',
			error: "This video can't be played",
		})
		render(Player)

		expect(screen.getByText("This video can't be played")).toBeInTheDocument()
	})

	it('collapses when Escape is pressed in the expanded panel', async () => {
		Object.assign(player, {
			current: song,
			queue: [song],
			index: 0,
			status: 'paused',
			expanded: true,
		})
		render(Player)

		screen.getByRole('button', { name: 'Collapse player' }).focus()
		await userEvent.keyboard('{Escape}')

		expect(toggleExpandedMock).toHaveBeenCalled()
	})
})
