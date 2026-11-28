import { getTaste, type Taste } from '#lib/api.js'

// 'none' means no taste is saved; Discover then asks for one.
export type TasteStatus = 'loading' | 'none' | 'ready' | 'error'

export interface TasteState {
	status: TasteStatus
	current: Taste | null
	error: string | null
}

export const taste: TasteState = $state({
	status: 'loading',
	current: null,
	error: null,
})

// Ignores a response that a newer load or a profile switch has outdated.
let loadGeneration = 0

export async function loadTaste() {
	const generation = ++loadGeneration
	taste.status = 'loading'
	taste.error = null
	try {
		const result = await getTaste()
		if (generation !== loadGeneration) return
		taste.current = result
		taste.status = result ? 'ready' : 'none'
	} catch (error) {
		if (generation !== loadGeneration) return
		taste.error =
			error instanceof Error ? error.message : 'Could not load your taste'
		taste.status = 'error'
	}
}

export function saveTasteResult(saved: Taste) {
	taste.current = saved
	taste.status = 'ready'
	taste.error = null
}

export function clearTaste() {
	taste.current = null
	taste.status = 'none'
	taste.error = null
}
