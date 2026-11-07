import type { ModelList, ModelStatus } from '#lib/api.js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { listModelsMock, startModelDownloadMock, removeModelMock, toastMock } =
	vi.hoisted(() => ({
		listModelsMock: vi.fn(),
		startModelDownloadMock: vi.fn(),
		removeModelMock: vi.fn(),
		toastMock: { error: vi.fn(), success: vi.fn() },
	}))

vi.mock('#lib/api.js', () => ({
	listModels: listModelsMock,
	startModelDownload: startModelDownloadMock,
	removeModel: removeModelMock,
}))
vi.mock('svelte-sonner', () => ({ toast: toastMock }))

import { run } from '#lib/run.svelte.js'
import {
	downloadModel,
	getActiveDownloads,
	loadModelCache,
	modelCache,
	removeModelFiles,
	watchModelCache,
} from './modelCache.svelte'

const MOSS = 'FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit'
const QWEN = 'Qwen/Qwen3-8B-MLX-4bit'

function makeStatus(
	id: string,
	overrides: Partial<ModelStatus> = {}
): ModelStatus {
	return {
		id,
		downloaded: false,
		size_bytes: 1000,
		download: null,
		...overrides,
	}
}

function makeDownloading(
	state: 'pending' | 'downloading' | 'failed' = 'downloading'
): NonNullable<ModelStatus['download']> {
	return {
		state,
		downloaded_bytes: 400,
		total_bytes: 1000,
		bytes_per_second: 50,
		seconds_remaining: 12,
		error: state === 'failed' ? 'network down' : null,
	}
}

function makeList(items: ModelStatus[], busy = false): ModelList {
	return { items, busy }
}

beforeEach(() => {
	vi.clearAllMocks()
	modelCache.status = 'loading'
	modelCache.items = []
	modelCache.busy = false
	modelCache.error = null
	modelCache.removing = []
	run.phase = 'idle'
	listModelsMock.mockResolvedValue(
		makeList([makeStatus(QWEN), makeStatus(MOSS)])
	)
})

afterEach(() => {
	vi.useRealTimers()
})

describe('loadModelCache', () => {
	it('stores the models and whether the API is busy', async () => {
		listModelsMock.mockResolvedValue(makeList([makeStatus(QWEN)], true))

		await loadModelCache()

		expect(modelCache.status).toBe('ready')
		expect(modelCache.items.map((item) => item.id)).toEqual([QWEN])
		expect(modelCache.busy).toBe(true)
	})

	it('reports an error and recovers when loaded again', async () => {
		listModelsMock.mockRejectedValueOnce(new Error('Request failed (500)'))

		await loadModelCache()
		expect(modelCache.status).toBe('error')
		expect(modelCache.error).toBe('Request failed (500)')

		const retry = loadModelCache()
		expect(modelCache.status).toBe('loading')
		await retry
		expect(modelCache.status).toBe('ready')
		expect(modelCache.error).toBeNull()
	})

	it('keeps the last known models when a refresh fails', async () => {
		await loadModelCache()
		listModelsMock.mockRejectedValueOnce(new Error('offline'))

		await loadModelCache()

		expect(modelCache.status).toBe('ready')
		expect(modelCache.items).toHaveLength(2)
	})

	it('toasts when a download that was running fails', async () => {
		listModelsMock.mockResolvedValueOnce(
			makeList([makeStatus(MOSS, { download: makeDownloading() })])
		)
		await loadModelCache()
		listModelsMock.mockResolvedValueOnce(
			makeList([makeStatus(MOSS, { download: makeDownloading('failed') })])
		)

		await loadModelCache()

		expect(toastMock.error).toHaveBeenCalledWith(
			'MOSS Music 8B Instruct (MLX 5-bit): network down'
		)
	})

	it('does not toast a failure that was already there on load', async () => {
		listModelsMock.mockResolvedValue(
			makeList([makeStatus(MOSS, { download: makeDownloading('failed') })])
		)

		await loadModelCache()

		expect(toastMock.error).not.toHaveBeenCalled()
	})
})

describe('getActiveDownloads', () => {
	it('lists pending and downloading models with their progress, in API order', async () => {
		listModelsMock.mockResolvedValue(
			makeList([
				makeStatus(QWEN, { download: makeDownloading('pending') }),
				makeStatus(MOSS, { download: makeDownloading() }),
			])
		)
		await loadModelCache()

		expect(getActiveDownloads()).toMatchObject([
			{ model: QWEN, state: 'pending', total_bytes: 1000 },
			{ model: MOSS, state: 'downloading', downloaded_bytes: 400 },
		])
	})

	it('leaves out idle, downloaded and failed models', async () => {
		listModelsMock.mockResolvedValue(
			makeList([
				makeStatus(QWEN, { downloaded: true }),
				makeStatus(MOSS, { download: makeDownloading('failed') }),
			])
		)
		await loadModelCache()

		expect(getActiveDownloads()).toEqual([])
	})
})

describe('downloadModel', () => {
	it('shows the returned pending state right away', async () => {
		await loadModelCache()
		startModelDownloadMock.mockResolvedValue(
			makeStatus(MOSS, { download: makeDownloading('pending') })
		)

		await downloadModel(MOSS)

		expect(startModelDownloadMock).toHaveBeenCalledWith(MOSS)
		expect(getActiveDownloads().map((item) => item.model)).toEqual([MOSS])
	})

	it('toasts the server message and reloads when the request is rejected', async () => {
		await loadModelCache()
		startModelDownloadMock.mockRejectedValue(
			new Error('Model is already downloaded')
		)
		listModelsMock.mockClear()

		await downloadModel(MOSS)

		expect(toastMock.error).toHaveBeenCalledWith('Model is already downloaded')
		expect(listModelsMock).toHaveBeenCalled()
	})
})

describe('removeModelFiles', () => {
	it('removes the model, toasts, and reloads the list', async () => {
		await loadModelCache()
		removeModelMock.mockResolvedValue(undefined)
		listModelsMock.mockClear()

		const removal = removeModelFiles(MOSS)
		expect(modelCache.removing).toEqual([MOSS])
		await removal

		expect(removeModelMock).toHaveBeenCalledWith(MOSS)
		expect(toastMock.success).toHaveBeenCalledWith(
			'Removed MOSS Music 8B Instruct (MLX 5-bit)'
		)
		expect(listModelsMock).toHaveBeenCalledOnce()
		expect(modelCache.removing).toEqual([])
	})

	it('toasts the server message when the removal is rejected', async () => {
		await loadModelCache()
		removeModelMock.mockRejectedValue(
			new Error('Wait for the current run or download to finish')
		)

		await removeModelFiles(MOSS)

		expect(toastMock.error).toHaveBeenCalledWith(
			'Wait for the current run or download to finish'
		)
		expect(toastMock.success).not.toHaveBeenCalled()
		expect(modelCache.removing).toEqual([])
	})

	it('ignores a second removal of the same model while one is in flight', async () => {
		await loadModelCache()
		removeModelMock.mockReturnValue(new Promise(() => {}))

		void removeModelFiles(MOSS)
		await removeModelFiles(MOSS)

		expect(removeModelMock).toHaveBeenCalledTimes(1)
	})
})

describe('watchModelCache', () => {
	const POLL_MS = 1000

	async function tick() {
		await vi.advanceTimersByTimeAsync(POLL_MS)
	}

	beforeEach(() => {
		vi.useFakeTimers()
	})

	it('loads once on start and does not poll while nothing is changing', async () => {
		const stop = watchModelCache()
		await tick()
		await tick()

		expect(listModelsMock).toHaveBeenCalledTimes(1)
		stop()
	})

	it('polls every second while a download is pending or downloading', async () => {
		listModelsMock.mockResolvedValue(
			makeList([makeStatus(MOSS, { download: makeDownloading() })])
		)
		const stop = watchModelCache()
		await vi.advanceTimersByTimeAsync(0)
		listModelsMock.mockClear()

		await tick()
		await tick()

		expect(listModelsMock).toHaveBeenCalledTimes(2)
		stop()
	})

	it('polls while a run is active, so a download it starts shows up', async () => {
		const stop = watchModelCache()
		await vi.advanceTimersByTimeAsync(0)
		listModelsMock.mockClear()

		run.phase = 'preparing'
		await tick()

		expect(listModelsMock).toHaveBeenCalledTimes(1)
		stop()
	})

	it('stops polling once the download finishes', async () => {
		listModelsMock.mockResolvedValueOnce(
			makeList([makeStatus(MOSS, { download: makeDownloading() })])
		)
		const stop = watchModelCache()
		await vi.advanceTimersByTimeAsync(0)
		listModelsMock.mockResolvedValue(
			makeList([makeStatus(MOSS, { downloaded: true })])
		)

		await tick()
		listModelsMock.mockClear()
		await tick()

		expect(listModelsMock).not.toHaveBeenCalled()
		expect(modelCache.items[0].downloaded).toBe(true)
		stop()
	})

	it('does not start a request while the previous one is still running', async () => {
		listModelsMock.mockResolvedValueOnce(
			makeList([makeStatus(MOSS, { download: makeDownloading() })])
		)
		const stop = watchModelCache()
		await vi.advanceTimersByTimeAsync(0)
		listModelsMock.mockReset()
		let finishRequest: (list: ModelList) => void = () => {}
		listModelsMock.mockReturnValue(
			new Promise<ModelList>((resolve) => (finishRequest = resolve))
		)

		await tick()
		await tick()

		expect(listModelsMock).toHaveBeenCalledTimes(1)
		// Lets the shared in-flight flag clear for the next test.
		finishRequest(makeList([]))
		await vi.advanceTimersByTimeAsync(0)
		stop()
	})

	it('shares one timer between watchers and stops after the last one leaves', async () => {
		listModelsMock.mockResolvedValue(
			makeList([makeStatus(MOSS, { download: makeDownloading() })])
		)
		const stopFirst = watchModelCache()
		const stopSecond = watchModelCache()
		await vi.advanceTimersByTimeAsync(0)
		listModelsMock.mockClear()

		await tick()
		expect(listModelsMock).toHaveBeenCalledTimes(1)

		stopFirst()
		await tick()
		expect(listModelsMock).toHaveBeenCalledTimes(2)

		stopSecond()
		await tick()
		expect(listModelsMock).toHaveBeenCalledTimes(2)
	})
})
