import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
	checkForUpdates,
	isNewerVersion,
	startAutoUpdateCheck,
	update,
} from './update.svelte'

const DAY_MS = 24 * 60 * 60 * 1000

function mockRelease(tag: string) {
	return new Response(JSON.stringify({ tag_name: tag }), { status: 200 })
}

describe('isNewerVersion', () => {
	it.each([
		['v0.2.0', '0.1.0', true],
		['0.1.1', '0.1.0', true],
		['0.10.0', '0.9.0', true],
		['v0.1.0', '0.1.0', false],
		['0.0.9', '0.1.0', false],
		['v1.0.0-rc1', '0.9.0', true],
	])('compares %s with %s', (latest, current, expected) => {
		expect(isNewerVersion(latest, current)).toBe(expected)
	})

	it('rejects a tag that is not a version', () => {
		expect(() => isNewerVersion('nightly', '0.1.0')).toThrow()
	})
})

describe('checkForUpdates', () => {
	const fetchMock = vi.fn()

	beforeEach(() => {
		vi.stubGlobal('fetch', fetchMock)
		vi.stubGlobal('__APP_VERSION__', '0.1.0')
		vi.stubEnv('VITE_UPDATE_TEST_VERSION', '')
		fetchMock.mockReset()
		Object.assign(update, {
			status: 'idle',
			latestVersion: null,
			error: null,
		})
	})

	afterEach(() => {
		vi.unstubAllGlobals()
		vi.unstubAllEnvs()
	})

	it('reports a newer release', async () => {
		fetchMock.mockResolvedValue(mockRelease('v0.2.0'))
		await checkForUpdates()

		expect(update).toMatchObject({
			status: 'available',
			latestVersion: '0.2.0',
			error: null,
		})
	})

	it('reports up to date for the same version', async () => {
		fetchMock.mockResolvedValue(mockRelease('v0.1.0'))
		await checkForUpdates()

		expect(update.status).toBe('up-to-date')
		expect(update.latestVersion).toBeNull()
	})

	it('treats a 404 (no stable release yet) as up to date', async () => {
		fetchMock.mockResolvedValue(new Response('{}', { status: 404 }))
		await checkForUpdates()

		expect(update.status).toBe('up-to-date')
	})

	it.each([
		[
			'a server error',
			() => Promise.resolve(new Response('', { status: 500 })),
		],
		['a network failure', () => Promise.reject(new Error('offline'))],
		['a malformed tag', () => Promise.resolve(mockRelease('nightly'))],
	])('shows %s from a manual check', async (_name, respond) => {
		fetchMock.mockImplementation(respond)
		await checkForUpdates()

		expect(update.status).toBe('error')
		expect(update.error).toBeTruthy()
	})

	it('hides failures from a silent check', async () => {
		fetchMock.mockRejectedValue(new Error('offline'))
		await checkForUpdates({ silent: true })

		expect(update.status).toBe('idle')
		expect(update.error).toBeNull()
	})

	it('keeps an update that was already found when a later check fails', async () => {
		fetchMock.mockResolvedValueOnce(mockRelease('v0.2.0'))
		await checkForUpdates({ silent: true })
		fetchMock.mockRejectedValueOnce(new Error('offline'))
		await checkForUpdates()

		expect(update.status).toBe('available')
		expect(update.latestVersion).toBe('0.2.0')
	})

	it('shares one request between overlapping checks', async () => {
		let resolve!: (response: Response) => void
		fetchMock.mockReturnValue(new Promise<Response>((r) => (resolve = r)))
		const first = checkForUpdates()
		const second = checkForUpdates()
		resolve(mockRelease('v0.2.0'))
		await Promise.all([first, second])

		expect(fetchMock).toHaveBeenCalledTimes(1)
		expect(update.status).toBe('available')
	})

	it('lets a manual check join a running silent check and report its failure', async () => {
		let reject!: (error: Error) => void
		fetchMock.mockReturnValue(new Promise<Response>((_, r) => (reject = r)))
		const silent = checkForUpdates({ silent: true })
		const manual = checkForUpdates()
		expect(update.status).toBe('checking')
		reject(new Error('offline'))
		await Promise.all([silent, manual])

		expect(fetchMock).toHaveBeenCalledTimes(1)
		expect(update.status).toBe('error')
		expect(update.error).toBe('offline')
	})

	it('uses the dev override as the latest version without calling GitHub', async () => {
		vi.stubEnv('VITE_UPDATE_TEST_VERSION', '9.9.9')
		await checkForUpdates()

		expect(fetchMock).not.toHaveBeenCalled()
		expect(update.latestVersion).toBe('9.9.9')
	})
})

describe('startAutoUpdateCheck', () => {
	const fetchMock = vi.fn()

	beforeEach(() => {
		vi.useFakeTimers()
		vi.stubGlobal('fetch', fetchMock)
		vi.stubGlobal('__APP_VERSION__', '0.1.0')
		vi.stubEnv('VITE_UPDATE_TEST_VERSION', '')
		fetchMock.mockReset()
		fetchMock.mockImplementation(() => Promise.resolve(mockRelease('v0.1.0')))
	})

	afterEach(() => {
		vi.useRealTimers()
		vi.unstubAllGlobals()
		vi.unstubAllEnvs()
	})

	it('checks at launch and every 24 hours until stopped', async () => {
		const stop = startAutoUpdateCheck()
		await vi.advanceTimersByTimeAsync(0)
		expect(fetchMock).toHaveBeenCalledTimes(1)

		await vi.advanceTimersByTimeAsync(DAY_MS)
		expect(fetchMock).toHaveBeenCalledTimes(2)

		stop()
		await vi.advanceTimersByTimeAsync(DAY_MS)
		expect(fetchMock).toHaveBeenCalledTimes(2)
	})
})
