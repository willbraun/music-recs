import { getTaste, type Taste } from '#lib/api.js'

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

export async function loadTaste() {
	taste.status = 'loading'
	taste.error = null
	try {
		const result = await getTaste()
		taste.current = result
		taste.status = result ? 'ready' : 'none'
	} catch (error) {
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
