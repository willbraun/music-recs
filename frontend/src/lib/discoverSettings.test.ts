import { beforeEach, describe, expect, it, vi } from 'vitest'

async function loadModule() {
	vi.resetModules()
	return import('./discoverSettings.svelte.js')
}

beforeEach(() => {
	localStorage.clear()
})

describe('discover settings', () => {
	it('uses the defaults when nothing is saved', async () => {
		const { discoverSettings } = await loadModule()

		expect(discoverSettings).toEqual({ count: 3, exploration: 50 })
	})

	it('restores saved settings after a restart', async () => {
		const first = await loadModule()
		first.setDiscoverCount(7)
		first.setDiscoverExploration(80)

		const { discoverSettings } = await loadModule()

		expect(discoverSettings).toEqual({ count: 7, exploration: 80 })
	})

	it('clamps values when saving and ignores unusable saved values', async () => {
		const first = await loadModule()
		first.setDiscoverCount(500)
		first.setDiscoverExploration(-5)
		expect(first.discoverSettings).toEqual({ count: 50, exploration: 0 })

		localStorage.setItem('music-recs:discover-count', 'abc')
		localStorage.setItem('music-recs:discover-exploration', '250')
		const { discoverSettings } = await loadModule()

		expect(discoverSettings).toEqual({ count: 3, exploration: 100 })
	})
})
