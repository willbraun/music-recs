export type UpdateStatus =
	'idle' | 'checking' | 'available' | 'up-to-date' | 'error'

export interface UpdateState {
	status: UpdateStatus
	latestVersion: string | null
	error: string | null
}

export const RELEASES_URL =
	'https://github.com/willbraun/music-recs/releases/latest'
const LATEST_RELEASE_API =
	'https://api.github.com/repos/willbraun/music-recs/releases/latest'
const CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000
// A manual check shows "Checking..." for at least this long, so the click visibly does something.
const MIN_CHECKING_MS = 1000

export const update: UpdateState = $state({
	status: 'idle',
	latestVersion: null,
	error: null,
})

function parseVersion(version: string): number[] | null {
	const match = /^v?(\d+)\.(\d+)\.(\d+)/.exec(version.trim())
	return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : null
}

// Compares X.Y.Z numerically; a prerelease suffix is ignored, as /releases/latest never returns one.
export function isNewerVersion(latest: string, current: string): boolean {
	const a = parseVersion(latest)
	const b = parseVersion(current)
	if (!a || !b) throw new Error(`Unrecognized version: ${latest} / ${current}`)
	for (let i = 0; i < 3; i++) {
		if (a[i] !== b[i]) return a[i] > b[i]
	}
	return false
}

// null means there is no stable release yet, which GitHub reports as a 404.
async function fetchLatestVersion(): Promise<string | null> {
	// Dev only: pretend this version is the latest release, to try the UI without publishing.
	const override = import.meta.env.DEV
		? import.meta.env.VITE_UPDATE_TEST_VERSION
		: undefined
	if (override) return override

	const response = await fetch(LATEST_RELEASE_API, {
		headers: { Accept: 'application/vnd.github+json' },
	})
	if (response.status === 404) return null
	if (!response.ok) throw new Error(`GitHub returned ${response.status}`)
	const release: { tag_name?: unknown } = await response.json()
	if (typeof release.tag_name !== 'string') {
		throw new Error('GitHub returned an unexpected response')
	}
	return release.tag_name
}

let inFlight: Promise<void> | null = null
let reportErrors = false
let manualCheckStartedAt = 0

function waitForMinimumChecking(): Promise<void> {
	if (!reportErrors) return Promise.resolve()
	const remaining = MIN_CHECKING_MS - (Date.now() - manualCheckStartedAt)
	return new Promise((resolve) => setTimeout(resolve, Math.max(0, remaining)))
}

async function runCheck() {
	try {
		const latest = await fetchLatestVersion().finally(waitForMinimumChecking)
		if (latest && isNewerVersion(latest, __APP_VERSION__)) {
			update.latestVersion = latest.replace(/^v/, '')
			update.status = 'available'
		} else {
			update.latestVersion = null
			update.status = 'up-to-date'
		}
		update.error = null
	} catch (error) {
		if (reportErrors) {
			update.status = update.latestVersion ? 'available' : 'error'
			update.error =
				error instanceof Error ? error.message : 'Could not check for updates'
		}
	} finally {
		inFlight = null
		reportErrors = false
	}
}

// A silent check (the automatic one) never reports failures. A manual check made while one is
// running joins it and reports its result. A failure keeps any update already found.
export function checkForUpdates({ silent = false } = {}): Promise<void> {
	if (!silent) {
		reportErrors = true
		manualCheckStartedAt = Date.now()
		update.status = 'checking'
		update.error = null
	}
	inFlight ??= runCheck()
	return inFlight
}

// Checks now and then every 24 hours while the app stays open; returns a function that stops it.
export function startAutoUpdateCheck(): () => void {
	void checkForUpdates({ silent: true })
	const timer = setInterval(
		() => void checkForUpdates({ silent: true }),
		CHECK_INTERVAL_MS
	)
	return () => clearInterval(timer)
}
