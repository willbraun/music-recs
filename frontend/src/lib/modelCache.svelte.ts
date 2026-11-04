import {
	listModels,
	removeModel,
	startModelDownload,
	type ModelDownloadItem,
	type ModelList,
	type ModelStatus,
} from '#lib/api.js'
import { findModel } from '#lib/models.js'
import { run } from '#lib/run.svelte.js'
import { toast } from 'svelte-sonner'

// Shared by the Models page and the Discover page so a download shows the same progress wherever it was started.
export type ModelCacheStatus = 'loading' | 'ready' | 'error'

export interface ModelCacheState {
	status: ModelCacheStatus
	items: ModelStatus[]
	busy: boolean
	error: string | null
	// Ids whose removal request is in flight.
	removing: string[]
}

const POLL_MS = 1000

export const modelCache: ModelCacheState = $state({
	status: 'loading',
	items: [],
	busy: false,
	error: null,
	removing: [],
})

export function isDownloadActive(item: ModelStatus | undefined): boolean {
	return (
		item?.download?.state === 'pending' ||
		item?.download?.state === 'downloading'
	)
}

// The API lists models in a fixed order, so the cards and panels do not jump around.
export function getActiveDownloads(): ModelDownloadItem[] {
	return modelCache.items.flatMap(({ id, download }) =>
		download &&
		(download.state === 'pending' || download.state === 'downloading')
			? [{ ...download, model: id, state: download.state }]
			: []
	)
}

function applyList(list: ModelList) {
	for (const item of list.items) {
		const before = modelCache.items.find((existing) => existing.id === item.id)
		if (isDownloadActive(before) && item.download?.state === 'failed')
			toast.error(
				`${findModel(item.id).name}: ${item.download.error ?? 'Download failed'}`
			)
	}
	modelCache.items = list.items
	modelCache.busy = list.busy
	modelCache.status = 'ready'
	modelCache.error = null
}

export async function loadModelCache() {
	if (modelCache.status === 'error') modelCache.status = 'loading'
	try {
		applyList(await listModels())
	} catch (error) {
		// A failed refresh keeps showing the last known state.
		if (modelCache.status === 'ready') return
		modelCache.error =
			error instanceof Error ? error.message : 'Could not load the models'
		modelCache.status = 'error'
	}
}

export async function downloadModel(id: string) {
	try {
		const item = await startModelDownload(id)
		const index = modelCache.items.findIndex((existing) => existing.id === id)
		if (index !== -1) modelCache.items[index] = item
	} catch (error) {
		toast.error(
			error instanceof Error ? error.message : 'Could not start the download'
		)
		void loadModelCache()
	}
}

export async function removeModelFiles(id: string) {
	if (modelCache.removing.includes(id)) return
	modelCache.removing.push(id)
	try {
		await removeModel(id)
		toast.success(`Removed ${findModel(id).name}`)
	} catch (error) {
		toast.error(
			error instanceof Error ? error.message : 'Could not remove the model'
		)
	} finally {
		modelCache.removing = modelCache.removing.filter((other) => other !== id)
		await loadModelCache()
	}
}

let watcherCount = 0
let timer: ReturnType<typeof setInterval> | undefined
let isRefreshing = false

// Downloads can start from a run on the Discover page, so poll while a run is active as well.
function isChangePossible(): boolean {
	return (
		run.phase === 'preparing' ||
		run.phase === 'streaming' ||
		modelCache.items.some(isDownloadActive)
	)
}

async function refreshWhileChanging() {
	if (isRefreshing || !isChangePossible()) return
	isRefreshing = true
	try {
		await loadModelCache()
	} finally {
		isRefreshing = false
	}
}

// Loads the models and keeps them fresh while a download may be running; call the result to stop.
export function watchModelCache(): () => void {
	void loadModelCache()
	watcherCount++
	if (watcherCount === 1) timer = setInterval(refreshWhileChanging, POLL_MS)
	return () => {
		watcherCount--
		if (watcherCount === 0) clearInterval(timer)
	}
}
