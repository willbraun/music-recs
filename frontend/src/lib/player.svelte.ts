import type { Song } from '#lib/api.js'
import { toast } from 'svelte-sonner'

export type PlayerStatus = 'idle' | 'loading' | 'playing' | 'paused' | 'error'

export interface PlayerState {
	current: Song | null
	queue: Song[]
	index: number
	// Which list the queue was built from, so late additions only join the matching queue.
	queueOrigin: string | null
	status: PlayerStatus
	position: number
	duration: number
	volume: number
	muted: boolean
	expanded: boolean
	error: string | null
}

interface YouTubePlayer {
	loadVideoById(videoId: string): void
	playVideo(): void
	pauseVideo(): void
	seekTo(seconds: number, allowSeekAhead: boolean): void
	getCurrentTime(): number
	getDuration(): number
	setVolume(volume: number): void
	mute(): void
	unMute(): void
	destroy(): void
}

interface YouTubeApi {
	Player: new (
		element: HTMLElement,
		options: {
			width: string
			height: string
			playerVars: Record<string, string | number>
			events: {
				onReady: () => void
				onStateChange: (event: { data: number }) => void
				onError: (event: { data: number }) => void
			}
		}
	) => YouTubePlayer
}

interface YouTubeWindow {
	YT?: YouTubeApi
	onYouTubeIframeAPIReady?: () => void
}

const YT_SCRIPT_URL = 'https://www.youtube.com/iframe_api'
const YT_STATE = { ENDED: 0, PLAYING: 1, PAUSED: 2, BUFFERING: 3 }
const VOLUME_KEY = 'music-recs:volume'
const MUTED_KEY = 'music-recs:muted'
const DEFAULT_VOLUME = 80
const POLL_INTERVAL_MS = 250
// Previous restarts the current song once it has played longer than this.
const RESTART_THRESHOLD_SECONDS = 3

function readStoredVolume(): number {
	const stored = Number(localStorage.getItem(VOLUME_KEY))
	if (localStorage.getItem(VOLUME_KEY) === null || Number.isNaN(stored)) {
		return DEFAULT_VOLUME
	}
	return Math.min(100, Math.max(0, stored))
}

export const player: PlayerState = $state({
	current: null,
	queue: [],
	index: -1,
	queueOrigin: null,
	status: 'idle',
	position: 0,
	duration: 0,
	volume: readStoredVolume(),
	muted: localStorage.getItem(MUTED_KEY) === 'true',
	expanded: false,
	error: null,
})

let host: HTMLElement | null = null
let instance: YouTubePlayer | null = null
let instancePromise: Promise<YouTubePlayer> | null = null
let apiPromise: Promise<YouTubeApi> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let loadToken = 0
// True from a track change until the new video plays, so the old video's end-screen replay is inaudible.
let isSilenced = false
let isMediaSessionRegistered = false

export function attachPlayerHost(element: HTMLElement) {
	host = element
}

export function detachPlayerHost() {
	stopPolling()
	instance?.destroy()
	instance = null
	instancePromise = null
	host = null
	isSilenced = false
}

function loadYouTubeApi(): Promise<YouTubeApi> {
	const youtubeWindow = window as unknown as YouTubeWindow
	if (youtubeWindow.YT?.Player) return Promise.resolve(youtubeWindow.YT)
	if (apiPromise) return apiPromise

	apiPromise = new Promise<YouTubeApi>((resolve, reject) => {
		youtubeWindow.onYouTubeIframeAPIReady = () => {
			if (youtubeWindow.YT) resolve(youtubeWindow.YT)
		}
		const script = document.createElement('script')
		script.src = YT_SCRIPT_URL
		script.async = true
		script.onerror = () => {
			apiPromise = null
			script.remove()
			reject(new Error('Could not load the YouTube player'))
		}
		document.head.append(script)
	})
	return apiPromise
}

function createInstance(): Promise<YouTubePlayer> {
	// One player for the whole app; moving or recreating the iframe reloads it and stops playback.
	instancePromise ??= loadYouTubeApi()
		.then(
			(api) =>
				new Promise<YouTubePlayer>((resolve, reject) => {
					if (!host) {
						reject(new Error('Player is not mounted'))
						return
					}
					// YT.Player replaces its target element, so give it a throwaway child.
					const target = document.createElement('div')
					host.append(target)
					const created: YouTubePlayer = new api.Player(target, {
						width: '100%',
						height: '100%',
						playerVars: {
							controls: 0,
							playsinline: 1,
							rel: 0,
							modestbranding: 1,
							origin: window.location.origin,
						},
						events: {
							onReady: () => resolve(created),
							onStateChange: handleStateChange,
							onError: handleError,
						},
					})
				})
		)
		.catch((error) => {
			instancePromise = null
			throw error
		})
	return instancePromise
}

function applyVolume() {
	if (!instance) return
	instance.setVolume(isSilenced ? 0 : player.volume)
	if (player.muted) instance.mute()
	else instance.unMute()
}

function startPolling() {
	if (pollTimer) return
	pollTimer = setInterval(syncProgress, POLL_INTERVAL_MS)
}

function stopPolling() {
	if (!pollTimer) return
	clearInterval(pollTimer)
	pollTimer = null
}

function syncProgress() {
	if (!instance) return
	player.position = instance.getCurrentTime() || 0
	player.duration = instance.getDuration() || 0
}

function updateMediaSession(song: Song) {
	// Lets hardware media keys and OS controls drive the player.
	if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return
	const artwork = song.album_art_url ?? song.thumbnail_url
	navigator.mediaSession.metadata = new MediaMetadata({
		title: song.title,
		artist: song.artist,
		artwork: artwork ? [{ src: artwork }] : [],
	})
	if (isMediaSessionRegistered) return
	isMediaSessionRegistered = true
	navigator.mediaSession.setActionHandler('play', () => {
		if (player.status !== 'playing') togglePlayback()
	})
	navigator.mediaSession.setActionHandler('pause', () => {
		if (player.status === 'playing') togglePlayback()
	})
	navigator.mediaSession.setActionHandler('previoustrack', playPrevious)
	navigator.mediaSession.setActionHandler('nexttrack', playNext)
}

async function startTrack(index: number) {
	const song = player.queue[index]
	if (!song) return
	const token = ++loadToken
	player.index = index
	player.current = song
	player.status = 'loading'
	player.position = 0
	player.duration = 0
	player.error = null
	updateMediaSession(song)

	if (instance) {
		isSilenced = true
		applyVolume()
	}

	try {
		const created = await createInstance()
		if (token !== loadToken) return
		instance = created
		applyVolume()
		created.loadVideoById(song.video_id)
	} catch (error) {
		if (token !== loadToken) return
		const message =
			error instanceof Error ? error.message : 'Could not play this song'
		player.status = 'error'
		player.error = message
		toast.error(message)
	}
}

function handleStateChange(event: { data: number }) {
	switch (event.data) {
		case YT_STATE.PLAYING:
			player.status = 'playing'
			if (isSilenced) {
				isSilenced = false
				applyVolume()
			}
			syncProgress()
			startPolling()
			break
		case YT_STATE.PAUSED:
			player.status = 'paused'
			stopPolling()
			syncProgress()
			break
		case YT_STATE.BUFFERING:
			player.status = 'loading'
			break
		case YT_STATE.ENDED:
			stopPolling()
			if (player.index < player.queue.length - 1) {
				playNext()
			} else {
				player.status = 'paused'
				syncProgress()
			}
			break
	}
}

function handleError(event: { data: number }) {
	stopPolling()
	const song = player.current
	// 101 and 150 mean the owner disabled embedding; 2, 5 and 100 are invalid, player error, or removed video.
	const isEmbedBlocked = event.data === 101 || event.data === 150
	const message = isEmbedBlocked
		? "This video can't be embedded"
		: "This video can't be played"
	const hasNext = player.index < player.queue.length - 1

	if (isEmbedBlocked && song) {
		toast.error(message, {
			action: {
				label: 'Open on YouTube',
				onClick: () => window.open(song.url, '_blank', 'noopener,noreferrer'),
			},
		})
	} else {
		toast.error(message)
	}

	if (hasNext) {
		void startTrack(player.index + 1)
	} else {
		player.status = 'error'
		player.error = message
	}
}

export function playSong(song: Song, queue: Song[] = [song], origin?: string) {
	// The queue is a snapshot: later filter or page changes do not alter it.
	const index = queue.findIndex((item) => item.video_id === song.video_id)
	player.queue = index === -1 ? [song] : [...queue]
	player.queueOrigin = origin ?? null
	void startTrack(index === -1 ? 0 : index)
}

export function appendToQueue(songs: Song[], origin?: string) {
	if (origin !== undefined && player.queueOrigin !== origin) return
	const known = new Set(player.queue.map((song) => song.video_id))
	for (const song of songs) {
		if (known.has(song.video_id)) continue
		known.add(song.video_id)
		player.queue.push(song)
	}
}

export function togglePlayback() {
	if (!player.current) return
	if (player.status === 'playing') instance?.pauseVideo()
	else if (player.status === 'paused') instance?.playVideo()
	else if (player.status === 'error') void startTrack(player.index)
}

export function playNext() {
	if (player.index < player.queue.length - 1) void startTrack(player.index + 1)
}

export function playPrevious() {
	if (!player.current) return
	if (player.position > RESTART_THRESHOLD_SECONDS || player.index === 0) {
		seekTo(0)
		return
	}
	void startTrack(player.index - 1)
}

export function seekTo(seconds: number) {
	instance?.seekTo(seconds, true)
	player.position = seconds
}

export function setVolume(volume: number) {
	player.volume = Math.min(100, Math.max(0, Math.round(volume)))
	if (player.volume > 0) player.muted = false
	localStorage.setItem(VOLUME_KEY, String(player.volume))
	localStorage.setItem(MUTED_KEY, String(player.muted))
	applyVolume()
}

export function toggleMute() {
	player.muted = !player.muted
	localStorage.setItem(MUTED_KEY, String(player.muted))
	applyVolume()
}

export function toggleExpanded() {
	player.expanded = !player.expanded
}
