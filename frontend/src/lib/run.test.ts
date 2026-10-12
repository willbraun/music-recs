import type { RunEvent, Song } from '#lib/api.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { startRunMock, openRunEventsMock, toastErrorMock } = vi.hoisted(() => ({
	startRunMock: vi.fn(),
	openRunEventsMock: vi.fn(),
	toastErrorMock: vi.fn(),
}))

vi.mock('#lib/api.js', () => ({ startRun: startRunMock, openRunEvents: openRunEventsMock }))
vi.mock('svelte-sonner', () => ({ toast: { error: toastErrorMock } }))

import { handleRunEvent, resetRun, resumeRun, run, startNewRun } from './run.svelte'

class FakeEventSource {
	static CLOSED = 2
	onmessage: ((message: { data: string }) => void) | null = null
	onerror: (() => void) | null = null
	readyState = 1
	close = vi.fn(() => {
		this.readyState = FakeEventSource.CLOSED
	})

	emit(event: RunEvent) {
		this.onmessage?.({ data: JSON.stringify(event) })
	}
}

function makeSong(video_id: string, recommended = true): Song & { type: 'scored'; index: number; tier: null } {
	return {
		type: 'scored',
		index: 1,
		tier: null,
		video_id,
		title: `Title ${video_id}`,
		artist: `Artist ${video_id}`,
		url: `https://www.youtube.com/watch?v=${video_id}`,
		recommended,
		confidence: 0.87,
		query: null,
	}
}

function makeAnalyzing(video_id: string): RunEvent {
	return {
		type: 'analyzing',
		index: 1,
		recommended_count: 0,
		video_id,
		title: `Title ${video_id}`,
		artist: `Artist ${video_id}`,
		url: `https://www.youtube.com/watch?v=${video_id}`,
		query: null,
		tier: null,
	}
}

let stream: FakeEventSource

beforeEach(() => {
	vi.clearAllMocks()
	vi.stubGlobal('EventSource', FakeEventSource)
	sessionStorage.clear()
	resetRun()
	stream = new FakeEventSource()
	openRunEventsMock.mockReturnValue(stream)
	startRunMock.mockResolvedValue({ id: 'run-1' })
})

describe('startNewRun', () => {
	it('enters preparing, requests the run, and opens the stream', async () => {
		const pending = startNewRun(5)
		expect(run.phase).toBe('preparing')
		expect(run.status).toBe('Waiting for the model...')
		await pending

		expect(startRunMock).toHaveBeenCalledWith(5)
		expect(openRunEventsMock).toHaveBeenCalledWith('run-1')
		expect(sessionStorage.getItem('music-recs:run-id')).toBe('run-1')
	})

	it('clears the previous results', async () => {
		await startNewRun(3)
		handleRunEvent(makeSong('a'))
		stream.emit({ type: 'done', analyzed: 1, recommended: 1, count: 3 })

		await startNewRun(3)

		expect(run.cards).toEqual([])
		expect(run.phase).toBe('preparing')
	})

	it('fails with the server message and a toast when the request is rejected', async () => {
		startRunMock.mockRejectedValue(new Error('Set your taste first'))

		await startNewRun(3)

		expect(run.phase).toBe('error')
		expect(run.error).toBe('Set your taste first')
		expect(toastErrorMock).toHaveBeenCalledWith('Set your taste first')
		expect(openRunEventsMock).not.toHaveBeenCalled()
	})

	it('ignores a start while a run is active', async () => {
		await startNewRun(3)
		await startNewRun(3)

		expect(startRunMock).toHaveBeenCalledTimes(1)
	})
})

describe('handleRunEvent', () => {
	it.each([
		[{ type: 'started', query: null, count: 3, exploration: 50 }, 'Reading your taste...'],
		[{ type: 'downloading_model', model: 'm' }, 'Downloading model (first run only)...'],
		[{ type: 'queries', queries: [] }, 'Searching...'],
		[{ type: 'fetching' }, 'Finding songs...'],
	] as [RunEvent, string][])('sets the status for %o', (event, status) => {
		handleRunEvent(event)
		expect(run.status).toBe(status)
	})

	it('adds a loading card on analyzing', () => {
		handleRunEvent(makeAnalyzing('a'))

		expect(run.status).toBe('Listening to Title a by Artist a...')
		expect(run.cards).toHaveLength(1)
		expect(run.cards[0]).toMatchObject({ kind: 'loading', video_id: 'a' })
	})

	it('turns the loading card into a song and starts streaming on a recommended score', () => {
		handleRunEvent({ type: 'started', query: null, count: 3, exploration: 50 })
		run.phase = 'preparing'
		handleRunEvent(makeAnalyzing('a'))
		handleRunEvent(makeSong('a'))

		expect(run.phase).toBe('streaming')
		expect(run.cards).toHaveLength(1)
		expect(run.cards[0]).toMatchObject({ kind: 'song', song: { video_id: 'a' } })
		expect(run.status).toBe('Found 1 of 3')
	})

	it('removes the loading card on a not recommended score', () => {
		handleRunEvent(makeAnalyzing('a'))
		handleRunEvent(makeSong('a', false))

		expect(run.cards).toEqual([])
		expect(run.phase).not.toBe('streaming')
	})

	it('keeps cards in the order songs finish analyzing', () => {
		handleRunEvent(makeAnalyzing('a'))
		handleRunEvent(makeSong('a'))
		handleRunEvent(makeAnalyzing('b'))
		handleRunEvent(makeSong('b'))
		handleRunEvent(makeAnalyzing('c'))

		expect(run.cards.map(card => (card.kind === 'song' ? card.song.video_id : `loading:${card.video_id}`))).toEqual([
			'a',
			'b',
			'loading:c',
		])
	})

	it('finishes on done and closes the stream', async () => {
		await startNewRun(3)
		stream.emit({ type: 'done', analyzed: 4, recommended: 2, count: 3 })

		expect(run.phase).toBe('done')
		expect(run.status).toBe('Found 2 of 3')
		expect(stream.close).toHaveBeenCalled()
	})

	it('fails on an error event with a toast and closes the stream', async () => {
		await startNewRun(3)
		stream.emit({ type: 'error', message: 'Model crashed' })

		expect(run.phase).toBe('error')
		expect(run.status).toBe('Model crashed')
		expect(toastErrorMock).toHaveBeenCalledWith('Model crashed')
		expect(stream.close).toHaveBeenCalled()
	})
})

describe('stream failures', () => {
	it('lets the browser reconnect while the stream is connecting', async () => {
		await startNewRun(3)
		stream.readyState = 0
		stream.onerror?.()

		expect(run.phase).toBe('preparing')
	})

	it('reports a lost connection when the stream is closed', async () => {
		await startNewRun(3)
		stream.readyState = FakeEventSource.CLOSED
		stream.onerror?.()

		expect(run.phase).toBe('error')
		expect(run.error).toBe('Lost connection to the server')
	})
})

describe('resumeRun', () => {
	it('does nothing without a saved run id', () => {
		resumeRun()

		expect(openRunEventsMock).not.toHaveBeenCalled()
		expect(run.phase).toBe('idle')
	})

	it('reopens the stream for the saved run id', () => {
		sessionStorage.setItem('music-recs:run-id', 'run-9')
		resumeRun()

		expect(openRunEventsMock).toHaveBeenCalledWith('run-9')
		expect(run.phase).toBe('preparing')
	})

	it('returns to idle and forgets the id when the run is unknown', () => {
		sessionStorage.setItem('music-recs:run-id', 'run-9')
		resumeRun()
		stream.readyState = FakeEventSource.CLOSED
		stream.onerror?.()

		expect(run.phase).toBe('idle')
		expect(sessionStorage.getItem('music-recs:run-id')).toBeNull()
		expect(toastErrorMock).not.toHaveBeenCalled()
	})
})
