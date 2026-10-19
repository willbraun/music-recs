import type { Song } from '#lib/api.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { toastErrorMock } = vi.hoisted(() => ({ toastErrorMock: vi.fn() }))
vi.mock('svelte-sonner', () => ({ toast: { error: toastErrorMock } }))

type Handlers = {
	onReady: () => void
	onStateChange: (event: { data: number }) => void
	onError: (event: { data: number }) => void
}

class FakePlayer {
	static last: FakePlayer
	handlers: Handlers
	loadVideoById = vi.fn()
	playVideo = vi.fn()
	pauseVideo = vi.fn()
	seekTo = vi.fn()
	setVolume = vi.fn()
	mute = vi.fn()
	unMute = vi.fn()
	destroy = vi.fn()
	getCurrentTime = vi.fn(() => 0)
	getDuration = vi.fn(() => 0)

	constructor(_element: HTMLElement, options: { events: Handlers }) {
		this.handlers = options.events
		FakePlayer.last = this
		queueMicrotask(() => this.handlers.onReady())
	}
}

function makeSong(id: string): Song {
	return {
		video_id: id,
		title: `Title ${id}`,
		artist: `Artist ${id}`,
		url: `https://www.youtube.com/watch?v=${id}`,
		recommended: true,
		confidence: 0.9,
		query: null,
	}
}

const songs = [makeSong('a'), makeSong('b'), makeSong('c')]

async function loadPlayer() {
	vi.resetModules()
	const module = await import('./player.svelte')
	module.attachPlayerHost(document.createElement('div'))
	return module
}

async function flush() {
	await new Promise((resolve) => setTimeout(resolve, 0))
}

beforeEach(() => {
	localStorage.clear()
	toastErrorMock.mockReset()
	;(window as unknown as { YT: unknown }).YT = { Player: FakePlayer }
})

describe('player', () => {
	it('loads the video and sets the queue when a song is played', async () => {
		const { player, playSong } = await loadPlayer()

		playSong(songs[1], songs)
		expect(player.status).toBe('loading')
		await flush()

		expect(FakePlayer.last.loadVideoById).toHaveBeenCalledWith('b')
		expect(player.current?.video_id).toBe('b')
		expect(player.index).toBe(1)
	})

	it('follows the state reported by the YouTube player', async () => {
		const { player, playSong } = await loadPlayer()
		playSong(songs[0], songs)
		await flush()

		FakePlayer.last.handlers.onStateChange({ data: 1 })
		expect(player.status).toBe('playing')
		FakePlayer.last.handlers.onStateChange({ data: 2 })
		expect(player.status).toBe('paused')
	})

	it('toggles playback through the YouTube player', async () => {
		const { player, playSong, togglePlayback } = await loadPlayer()
		playSong(songs[0], songs)
		await flush()
		FakePlayer.last.handlers.onStateChange({ data: 1 })

		togglePlayback()
		expect(FakePlayer.last.pauseVideo).toHaveBeenCalled()
		FakePlayer.last.handlers.onStateChange({ data: 2 })
		togglePlayback()
		expect(FakePlayer.last.playVideo).toHaveBeenCalled()
		expect(player.status).toBe('paused')
	})

	it('plays the next song when a video ends and stops at the end of the queue', async () => {
		const { player, playSong } = await loadPlayer()
		playSong(songs[1], songs)
		await flush()

		FakePlayer.last.handlers.onStateChange({ data: 0 })
		await flush()
		expect(player.current?.video_id).toBe('c')

		FakePlayer.last.handlers.onStateChange({ data: 0 })
		expect(player.current?.video_id).toBe('c')
		expect(player.status).toBe('paused')
	})

	it('silences the player between songs until the next video plays', async () => {
		const { playSong } = await loadPlayer()
		playSong(songs[0], songs)
		await flush()
		const fake = FakePlayer.last
		fake.handlers.onStateChange({ data: 1 })
		fake.setVolume.mockClear()

		fake.handlers.onStateChange({ data: 0 })
		await flush()
		expect(fake.setVolume).toHaveBeenLastCalledWith(0)
		expect(fake.loadVideoById).toHaveBeenLastCalledWith('b')

		fake.handlers.onStateChange({ data: 1 })
		expect(fake.setVolume).toHaveBeenLastCalledWith(80)
	})

	it('restarts the song when going back after 3 seconds, else plays the previous', async () => {
		const { player, playPrevious, playSong } = await loadPlayer()
		playSong(songs[1], songs)
		await flush()

		player.position = 10
		playPrevious()
		expect(FakePlayer.last.seekTo).toHaveBeenCalledWith(0, true)
		expect(player.current?.video_id).toBe('b')

		player.position = 1
		playPrevious()
		await flush()
		expect(player.current?.video_id).toBe('a')
	})

	it('skips to the next song with a toast when a video cannot be played', async () => {
		const { player, playSong } = await loadPlayer()
		playSong(songs[0], songs)
		await flush()

		FakePlayer.last.handlers.onError({ data: 100 })
		await flush()

		expect(toastErrorMock).toHaveBeenCalledWith("This video can't be played")
		expect(player.current?.video_id).toBe('b')
	})

	it('offers Open on YouTube when embedding is disabled and enters the error state at the end', async () => {
		const { player, playSong } = await loadPlayer()
		playSong(songs[2], songs)
		await flush()

		FakePlayer.last.handlers.onError({ data: 101 })

		expect(toastErrorMock).toHaveBeenCalledWith(
			"This video can't be embedded",
			expect.objectContaining({
				action: expect.objectContaining({ label: 'Open on YouTube' }),
			})
		)
		expect(player.status).toBe('error')
		expect(player.error).toBe("This video can't be embedded")
	})

	it('appends only unknown songs, and only to a matching queue origin', async () => {
		const { appendToQueue, player, playSong } = await loadPlayer()
		playSong(songs[0], [songs[0]], 'run')

		appendToQueue([songs[0], songs[1]], 'run')
		appendToQueue([songs[2]], 'other')

		expect(player.queue.map((song) => song.video_id)).toEqual(['a', 'b'])
	})

	it('saves volume and mute to localStorage and restores them', async () => {
		const first = await loadPlayer()
		first.setVolume(40)
		first.toggleMute()

		const second = await loadPlayer()
		expect(second.player.volume).toBe(40)
		expect(second.player.muted).toBe(true)
	})

	it('defaults the volume to 80', async () => {
		const { player } = await loadPlayer()

		expect(player.volume).toBe(80)
	})

	it('toggles the expanded flag without persisting it', async () => {
		const { player, toggleExpanded } = await loadPlayer()

		toggleExpanded()
		expect(player.expanded).toBe(true)
		expect(localStorage.length).toBe(0)
	})
})
