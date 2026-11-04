// Mirrors the API's Song; a `scored` run event carries the same fields. The artwork fields are null when no match.
export interface Song {
	video_id: string
	title: string
	artist: string
	url: string
	recommended: boolean
	confidence: number
	analyzed_at?: string
	query: string | null
	thumbnail_url?: string
	album_art_url?: string | null
	album?: string | null
	musicbrainz_recording_id?: string | null
	musicbrainz_release_group_id?: string | null
}

export type Tier = 'familiar' | 'adjacent' | 'adventurous'

// Progress of a model download; total_bytes and seconds_remaining are null while unknown.
export interface ModelDownload {
	model: string
	downloaded_bytes: number
	total_bytes: number | null
	bytes_per_second: number
	seconds_remaining: number | null
}

// pending: queued behind an earlier run or download; the API runs one at a time.
export type ModelDownloadState = 'pending' | 'downloading'

export type ModelDownloadItem = ModelDownload & { state: ModelDownloadState }

// Download progress is not part of RunEvent: runs and the Models page share it through GET /api/models.
export type RunEvent =
	| {
			type: 'started'
			query: string | null
			count: number
			exploration: number
	  }
	| { type: 'queries'; queries: { query: string; tier: Tier | null }[] }
	| { type: 'fetching' }
	| {
			type: 'analyzing'
			index: number
			recommended_count: number
			video_id: string
			title: string
			artist: string
			url: string
			query: string | null
			tier: Tier | null
			thumbnail_url?: string
			album_art_url?: string | null
	  }
	| ({ type: 'scored'; index: number; tier: Tier | null } & Song)
	| { type: 'done'; analyzed: number; recommended: number; count: number }
	| { type: 'error'; message: string }

export class ApiError extends Error {
	status: number

	constructor(message: string, status: number) {
		super(message)
		this.name = 'ApiError'
		this.status = status
	}
}

async function readErrorMessage(response: Response): Promise<string> {
	// detail is a string for errors the API raises itself; validation errors send a list, so use the generic message.
	try {
		const body = await response.json()
		if (typeof body?.detail === 'string') return body.detail
	} catch {
		// Fall through to the generic message.
	}
	return `Request failed (${response.status})`
}

export async function startRun(
	count: number,
	exploration: number
): Promise<{ id: string }> {
	const response = await fetch('/api/runs', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ count, exploration }),
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export interface SongPage {
	items: Song[]
	total: number
	page: number
	page_size: number
}

export async function listSongs(page = 1): Promise<SongPage> {
	const response = await fetch(`/api/songs?page=${page}`)
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export interface TasteProfile {
	liked_genres: string[]
	liked_artists: string[]
	disliked_genres: string[]
	disliked_artists: string[]
	notes: string
}

export interface Taste {
	profile: TasteProfile
	text: string
	updated_at: string
}

export async function getTaste(): Promise<Taste | null> {
	const response = await fetch('/api/taste')
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function saveTaste(profile: TasteProfile): Promise<Taste> {
	const response = await fetch('/api/taste', {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ profile }),
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export function openRunEvents(id: string): EventSource {
	return new EventSource(`/api/runs/${encodeURIComponent(id)}/events`)
}

// A failed download stays until the next attempt; the others end when the download finishes.
export interface ModelDownloadStatus extends Omit<ModelDownload, 'model'> {
	state: ModelDownloadState | 'failed'
	error: string | null
}

export interface ModelStatus {
	id: string
	downloaded: boolean
	// Null when unknown, such as when the Hugging Face Hub is unreachable.
	size_bytes: number | null
	download: ModelDownloadStatus | null
}

export interface ModelList {
	items: ModelStatus[]
	// A run or download is queued or running, so models cannot be removed.
	busy: boolean
}

export async function listModels(): Promise<ModelList> {
	const response = await fetch('/api/models')
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

// Ids contain a slash, which the API route takes as part of the path.
function getModelPath(id: string): string {
	return `/api/models/${id.split('/').map(encodeURIComponent).join('/')}`
}

export async function startModelDownload(id: string): Promise<ModelStatus> {
	const response = await fetch(`${getModelPath(id)}/download`, {
		method: 'POST',
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function removeModel(id: string): Promise<void> {
	const response = await fetch(getModelPath(id), { method: 'DELETE' })
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
}
