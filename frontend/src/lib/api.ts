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
			count: number
			exploration: number
	  }
	| { type: 'queries'; queries: { query: string; tier: Tier }[] }
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
			tier: Tier
			thumbnail_url?: string
			album_art_url?: string | null
			album?: string | null
	  }
	| ({ type: 'scored'; index: number; tier: Tier } & Song)
	| { type: 'done'; analyzed: number; recommended: number; count: number }
	| { type: 'cancelled' }
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

export interface Profile {
	id: number
	name: string
	// A single emoji.
	avatar: string
}

export type ProfileInput = Omit<Profile, 'id'>

// Songs, taste and runs act for this profile; the API reads it from the X-Profile-Id header.
let activeProfileId: number | null = null

export function setApiProfileId(id: number | null) {
	activeProfileId = id
}

export function getApiProfileId(): number | null {
	return activeProfileId
}

function fetchForProfile(
	input: string,
	init?: RequestInit,
	profileId: number | null = activeProfileId
): Promise<Response> {
	if (profileId === null) return fetch(input, init)
	const headers = new Headers(init?.headers)
	headers.set('X-Profile-Id', String(profileId))
	return fetch(input, { ...init, headers })
}

export async function startRun(
	count: number,
	exploration: number
): Promise<{ id: string }> {
	const response = await fetchForProfile('/api/runs', {
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
	const response = await fetchForProfile(`/api/songs?page=${page}`)
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
	const response = await fetchForProfile('/api/taste')
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function saveTaste(profile: TasteProfile): Promise<Taste> {
	const response = await fetchForProfile('/api/taste', {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ profile }),
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function cancelRun(
	id: string,
	profileId: number | null = activeProfileId
): Promise<void> {
	const response = await fetchForProfile(
		`/api/runs/${encodeURIComponent(id)}`,
		{ method: 'DELETE' },
		profileId
	)
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
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

export async function listProfiles(): Promise<Profile[]> {
	const response = await fetch('/api/profiles')
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return (await response.json()).items
}

export async function getProfile(id: number): Promise<Profile> {
	const response = await fetch(`/api/profiles/${id}`)
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function createProfile(input: ProfileInput): Promise<Profile> {
	const response = await fetch('/api/profiles', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(input),
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function updateProfile(
	id: number,
	input: ProfileInput
): Promise<Profile> {
	const response = await fetch(`/api/profiles/${id}`, {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(input),
	})
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
	return response.json()
}

export async function deleteProfile(id: number): Promise<void> {
	const response = await fetch(`/api/profiles/${id}`, { method: 'DELETE' })
	if (!response.ok)
		throw new ApiError(await readErrorMessage(response), response.status)
}
