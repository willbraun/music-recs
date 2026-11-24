export const MIN_COUNT = 1
export const MAX_COUNT = 50
export const DEFAULT_COUNT = 3
export const DEFAULT_EXPLORATION = 50

const COUNT_KEY = 'music-recs:discover-count'
const EXPLORATION_KEY = 'music-recs:discover-exploration'

function clamp(value: number, min: number, max: number): number {
	return Math.min(max, Math.max(min, Math.round(value)))
}

function readStored(key: string, fallback: number, min: number, max: number) {
	const raw = localStorage.getItem(key)
	if (raw === null) return fallback
	const stored = Number(raw)
	return Number.isNaN(stored) ? fallback : clamp(stored, min, max)
}

// Shared by every visit to Discover and saved so the choices survive restarting the app.
export const discoverSettings: { count: number; exploration: number } = $state({
	count: readStored(COUNT_KEY, DEFAULT_COUNT, MIN_COUNT, MAX_COUNT),
	exploration: readStored(EXPLORATION_KEY, DEFAULT_EXPLORATION, 0, 100),
})

export function setDiscoverCount(count: number) {
	discoverSettings.count = clamp(count, MIN_COUNT, MAX_COUNT)
	localStorage.setItem(COUNT_KEY, String(discoverSettings.count))
}

export function setDiscoverExploration(exploration: number) {
	discoverSettings.exploration = clamp(exploration, 0, 100)
	localStorage.setItem(EXPLORATION_KEY, String(discoverSettings.exploration))
}
