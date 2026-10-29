import {
	ApiError,
	openRunEvents,
	startRun,
	type RunEvent,
	type Song,
} from '#lib/api.js'
import { appendToQueue } from '#lib/player.svelte.js'
import { clearTaste } from '#lib/taste.svelte.js'
import { toast } from 'svelte-sonner'

// Tags the player queue built from this run's recommendations.
export const RUN_QUEUE_ORIGIN = 'run'

// preparing: requested, nothing recommended yet. streaming: at least one recommendation has arrived.
export type RunPhase = 'idle' | 'preparing' | 'streaming' | 'done' | 'error'

export type RunCard =
	| {
			kind: 'loading'
			video_id: string
			title: string
			artist: string
			thumbnail_url?: string
			album_art_url?: string | null
	  }
	| { kind: 'song'; song: Song }

export interface RunState {
	phase: RunPhase
	status: string
	count: number
	recommended: number
	cards: RunCard[]
	error: string | null
}

// Kept in sessionStorage so a reload can reattach; the server replays every event for a known run id.
const RUN_ID_KEY = 'music-recs:run-id'

function createInitialState(): RunState {
	return {
		phase: 'idle',
		status: '',
		count: 0,
		recommended: 0,
		cards: [],
		error: null,
	}
}

export const run: RunState = $state(createInitialState())

let source: EventSource | null = null
let receivedEvent = false

function saveRunId(id: string) {
	sessionStorage.setItem(RUN_ID_KEY, id)
}

function clearRunId() {
	sessionStorage.removeItem(RUN_ID_KEY)
}

export function closeRunStream() {
	source?.close()
	source = null
}

export function resetRun() {
	closeRunStream()
	clearRunId()
	receivedEvent = false
	Object.assign(run, createInitialState())
}

function failRun(message: string) {
	closeRunStream()
	run.phase = 'error'
	run.status = message
	run.error = message
	toast.error(message)
}

export function handleRunEvent(event: RunEvent) {
	switch (event.type) {
		case 'started':
			run.count = event.count
			run.status = 'Reading your taste...'
			break
		case 'downloading_model':
			run.status = 'Downloading model (first run only)...'
			break
		case 'queries':
			run.status = 'Searching...'
			break
		case 'fetching':
			run.status = 'Finding songs...'
			break
		case 'analyzing':
			run.status = `Listening to ${event.title} by ${event.artist}...`
			run.cards.push({
				kind: 'loading',
				video_id: event.video_id,
				title: event.title,
				artist: event.artist,
				thumbnail_url: event.thumbnail_url,
				album_art_url: event.album_art_url,
			})
			break
		case 'scored': {
			const index = run.cards.findIndex(
				(card) => card.kind === 'loading' && card.video_id === event.video_id
			)
			if (event.recommended) {
				const card: RunCard = { kind: 'song', song: event }
				if (index === -1) run.cards.push(card)
				else run.cards[index] = card
				run.recommended += 1
				appendToQueue([event], RUN_QUEUE_ORIGIN)
				if (run.phase === 'preparing') run.phase = 'streaming'
			} else if (index !== -1) {
				// Not-recommended songs are not shown here; they only appear on the Songs page.
				run.cards.splice(index, 1)
			}
			run.status = `Found ${run.recommended} of ${run.count}`
			break
		}
		case 'done':
			closeRunStream()
			run.phase = 'done'
			run.recommended = event.recommended
			run.count = event.count
			run.status = `Done`
			break
		case 'error':
			failRun(event.message)
			break
	}
}

function listenToRun(id: string, isResume: boolean) {
	closeRunStream()
	receivedEvent = false
	const stream = openRunEvents(id)
	source = stream

	stream.onmessage = (message) => {
		receivedEvent = true
		handleRunEvent(JSON.parse(message.data))
	}
	stream.onerror = () => {
		// The browser reconnects with Last-Event-ID on its own while the state is CONNECTING.
		if (stream.readyState !== EventSource.CLOSED) return
		if (isResume && !receivedEvent) {
			// A closed stream with no events means the server no longer knows the run (404).
			resetRun()
			return
		}
		failRun('Lost connection to the server')
	}
}

export async function startNewRun(count: number, exploration: number) {
	if (run.phase === 'preparing' || run.phase === 'streaming') return
	closeRunStream()
	Object.assign(run, createInitialState(), {
		phase: 'preparing',
		status: 'Waiting for the model...',
	})
	try {
		const { id } = await startRun(count, exploration)
		saveRunId(id)
		listenToRun(id, false)
	} catch (error) {
		// No taste is saved, so the taste gate sends the user to /taste without a toast.
		if (error instanceof ApiError && error.status === 409) {
			resetRun()
			clearTaste()
			return
		}
		failRun(error instanceof Error ? error.message : 'Could not start the run')
	}
}

export function resumeRun() {
	const id = sessionStorage.getItem(RUN_ID_KEY)
	if (!id || source) return
	Object.assign(run, createInitialState(), {
		phase: 'preparing',
		status: 'Waiting for the model...',
	})
	listenToRun(id, true)
}
