import { beforeEach, describe, expect, it, vi } from 'vitest'

const {
	resetRunMock,
	isRunActiveMock,
	cancelCurrentRunMock,
	stopPlayerMock,
	clearTasteMock,
	loadTasteMock,
} = vi.hoisted(() => ({
	resetRunMock: vi.fn(),
	isRunActiveMock: vi.fn(() => false),
	cancelCurrentRunMock: vi.fn(async () => {}),
	stopPlayerMock: vi.fn(),
	clearTasteMock: vi.fn(),
	loadTasteMock: vi.fn(),
}))

vi.mock('#lib/run.svelte.js', () => ({
	resetRun: resetRunMock,
	isRunActive: isRunActiveMock,
	cancelCurrentRun: cancelCurrentRunMock,
}))
vi.mock('#lib/player.svelte.js', () => ({ stopPlayer: stopPlayerMock }))
vi.mock('#lib/taste.svelte.js', () => ({
	clearTaste: clearTasteMock,
	loadTaste: loadTasteMock,
}))

const ANN = { id: 1, name: 'Ann', avatar: '🎸' }
const BOB = { id: 2, name: 'Bob', avatar: '🎹' }

function respondWith(body: unknown, status = 200) {
	return vi.fn(async () => new Response(JSON.stringify(body), { status }))
}

async function loadModule() {
	vi.resetModules()
	return {
		store: await import('./profiles.svelte.js'),
		api: await import('./api.js'),
	}
}

beforeEach(() => {
	sessionStorage.clear()
	vi.clearAllMocks()
	isRunActiveMock.mockReturnValue(false)
	vi.unstubAllGlobals()
})

describe('profiles', () => {
	it('starts with no active profile in a new tab', async () => {
		const { store } = await loadModule()

		expect(store.profiles.activeId).toBeNull()
	})

	it('restores the profile chosen earlier in the same tab', async () => {
		sessionStorage.setItem('music-recs:profile-id', '2')
		const { store } = await loadModule()
		vi.stubGlobal('fetch', respondWith({ items: [ANN, BOB] }))

		await store.loadProfiles()

		expect(store.profiles.status).toBe('ready')
		expect(store.getActiveProfile()).toEqual(BOB)
	})

	it('forgets a stored profile that no longer exists', async () => {
		sessionStorage.setItem('music-recs:profile-id', '9')
		const { store } = await loadModule()
		vi.stubGlobal('fetch', respondWith({ items: [ANN] }))

		await store.loadProfiles()

		expect(store.profiles.activeId).toBeNull()
		expect(sessionStorage.getItem('music-recs:profile-id')).toBeNull()
	})

	it('reports an error when the profiles cannot be loaded', async () => {
		const { store } = await loadModule()
		vi.stubGlobal('fetch', respondWith({ detail: 'Down' }, 500))

		await store.loadProfiles()

		expect(store.profiles.status).toBe('error')
		expect(store.profiles.error).toBe('Down')
	})

	it('switches profiles by clearing the old state and reloading the taste', async () => {
		const { store } = await loadModule()
		store.profiles.items = [ANN, BOB]

		store.selectProfile(2)

		expect(store.profiles.activeId).toBe(2)
		expect(sessionStorage.getItem('music-recs:profile-id')).toBe('2')
		expect(resetRunMock).toHaveBeenCalled()
		expect(stopPlayerMock).toHaveBeenCalled()
		expect(clearTasteMock).toHaveBeenCalled()
		expect(loadTasteMock).toHaveBeenCalledOnce()
	})

	it('does nothing when the active profile is selected again', async () => {
		const { store } = await loadModule()
		store.selectProfile(1)
		vi.clearAllMocks()

		store.selectProfile(1)

		expect(resetRunMock).not.toHaveBeenCalled()
		expect(loadTasteMock).not.toHaveBeenCalled()
	})

	it('sends the active profile with profile-scoped requests only', async () => {
		const { store, api } = await loadModule()
		const fetchMock = respondWith(null)
		vi.stubGlobal('fetch', fetchMock)
		store.selectProfile(2)

		await api.getTaste()
		await api.listModels().catch(() => {})

		const [, taste] = fetchMock.mock.calls[0] as unknown as [
			string,
			RequestInit,
		]
		expect(new Headers(taste.headers).get('X-Profile-Id')).toBe('2')
		expect(fetchMock.mock.calls[1]).toEqual(['/api/models'])
	})

	it('adds, renames and removes profiles, leaving the active one when another is removed', async () => {
		const { store } = await loadModule()
		store.profiles.items = [ANN]
		store.selectProfile(1)

		vi.stubGlobal('fetch', respondWith(BOB, 201))
		await store.addProfile({ name: 'Bob', avatar: '🎹' })
		expect(store.profiles.items).toEqual([ANN, BOB])

		vi.stubGlobal('fetch', respondWith({ ...BOB, name: 'Bobby' }))
		await store.saveProfile(2, { name: 'Bobby', avatar: '🎹' })
		expect(store.profiles.items[1].name).toBe('Bobby')

		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(null, { status: 204 }))
		)
		await store.removeProfile(2)
		expect(store.profiles.items).toEqual([ANN])
		expect(store.profiles.activeId).toBe(1)
	})

	it('clears the selection when the active profile is removed', async () => {
		const { store } = await loadModule()
		store.profiles.items = [ANN, BOB]
		store.selectProfile(1)
		vi.clearAllMocks()
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(null, { status: 204 }))
		)

		await store.removeProfile(1)

		expect(store.profiles.activeId).toBeNull()
		expect(store.profiles.items).toEqual([BOB])
		expect(resetRunMock).toHaveBeenCalled()
		expect(sessionStorage.getItem('music-recs:profile-id')).toBeNull()
	})

	describe('switching during a run', () => {
		it('asks before leaving a profile whose run is active', async () => {
			const { store } = await loadModule()
			store.selectProfile(1)
			vi.clearAllMocks()
			isRunActiveMock.mockReturnValue(true)

			expect(store.requestProfileSwitch(2)).toBe(false)

			expect(store.profiles.pendingSwitchId).toBe(2)
			expect(store.profiles.activeId).toBe(1)
			expect(cancelCurrentRunMock).not.toHaveBeenCalled()
		})

		it('stays on the current profile when the switch is dismissed', async () => {
			const { store } = await loadModule()
			store.selectProfile(1)
			isRunActiveMock.mockReturnValue(true)
			store.requestProfileSwitch(2)

			store.cancelProfileSwitch()

			expect(store.profiles.pendingSwitchId).toBeNull()
			expect(store.profiles.activeId).toBe(1)
		})

		it('cancels the run, then switches, once confirmed', async () => {
			const { store } = await loadModule()
			store.selectProfile(1)
			isRunActiveMock.mockReturnValue(true)
			store.requestProfileSwitch(2)

			expect(await store.confirmProfileSwitch()).toBe(true)

			expect(cancelCurrentRunMock).toHaveBeenCalledOnce()
			expect(store.profiles.activeId).toBe(2)
			expect(store.profiles.pendingSwitchId).toBeNull()
		})

		it('switches straight away when no run is active or the profile is unchanged', async () => {
			const { store } = await loadModule()
			isRunActiveMock.mockReturnValue(false)
			expect(store.requestProfileSwitch(1)).toBe(true)
			isRunActiveMock.mockReturnValue(true)

			expect(store.requestProfileSwitch(1)).toBe(true)
			expect(store.profiles.pendingSwitchId).toBeNull()
		})
	})
})
