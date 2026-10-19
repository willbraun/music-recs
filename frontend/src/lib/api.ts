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

export type RunEvent =
	| {
			type: 'started'
			query: string | null
			count: number
			exploration: number
	  }
	| { type: 'downloading_model'; model: string }
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

export function openRunEvents(id: string): EventSource {
	return new EventSource(`/api/runs/${encodeURIComponent(id)}/events`)
}
