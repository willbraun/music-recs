const API_BASE = window.API_BASE ?? ''
const YOUTUBE_PREFIX = 'https://www.youtube.com/'

const runForm = document.getElementById('run-form')
const runButton = runForm.querySelector('button')
const explorationValueEl = document.getElementById('exploration-value')
const statusEl = document.getElementById('status')
const resultsEl = document.getElementById('results')
const historyStatusEl = document.getElementById('history-status')
const historyListEl = document.getElementById('history-list')
const tasteForm = document.getElementById('taste-form')
const tasteIntroEl = document.getElementById('taste-intro')
const tasteStatusEl = document.getElementById('taste-status')
const LIST_FIELDS = ['liked_genres', 'liked_artists', 'disliked_genres', 'disliked_artists']
const HISTORY_PAGE_SIZE = 100
let requestedCount = 0
let hasTaste = false
let tasteLoaded = false

// Text goes in via textContent only: titles and descriptions come from YouTube and a model.
function createElement(tag, props = {}, ...children) {
	const node = Object.assign(document.createElement(tag), props)
	node.append(...children)
	return node
}

function setStatus(node, text, isError = false) {
	node.textContent = text
	node.className = isError ? 'error' : ''
}

function createSongLink(song) {
	const label = `${song.artist} - ${song.title}`
	if (!song.url.startsWith(YOUTUBE_PREFIX)) return createElement('span', {}, label)
	return createElement('a', { href: song.url, target: '_blank', rel: 'noopener' }, label)
}

function createSongItem(song, meta = '') {
	return createElement(
		'li',
		{ className: song.recommended ? 'recommended' : '' },
		createSongLink(song),
		createElement('span', { className: 'meta' }, meta),
	)
}

function parseList(text) {
	return text
		.split(',')
		.map(item => item.trim())
		.filter(Boolean)
}

function fillTasteForm(profile) {
	for (const field of LIST_FIELDS) tasteForm[field].value = (profile?.[field] ?? []).join(', ')
	tasteForm.notes.value = profile?.notes ?? ''
}

async function readError(res) {
	const body = await res.json().catch(() => null)
	return typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status})`
}

async function loadTaste() {
	setStatus(tasteStatusEl, 'Loading...')
	tasteForm.querySelector('button').disabled = true
	try {
		const res = await fetch(`${API_BASE}/api/taste`)
		if (!res.ok) throw new Error(await readError(res))
		const taste = await res.json()
		tasteLoaded = true
		hasTaste = taste !== null
		fillTasteForm(taste?.profile)
		setStatus(tasteStatusEl, '')
		tasteForm.querySelector('button').disabled = false
		tasteIntroEl.hidden = hasTaste
		if (!hasTaste) showView('taste')
	} catch (e) {
		setStatus(tasteStatusEl, `Could not load taste: ${e.message}`, true)
	}
}

function showView(name) {
	if (!hasTaste && name !== 'taste') {
		name = 'taste'
		tasteIntroEl.hidden = false
	}
	for (const button of document.querySelectorAll('nav button')) {
		button.classList.toggle('active', button.dataset.view === name)
	}
	for (const section of document.querySelectorAll('main > section')) {
		section.hidden = section.id !== name
	}
	if (name === 'history') loadHistory()
	// Retry a failed first load so the form never shows blanks that a save would write over the real taste.
	if (name === 'taste' && !tasteLoaded) loadTaste()
}

async function loadHistory() {
	setStatus(historyStatusEl, 'Loading...')
	try {
		const res = await fetch(`${API_BASE}/api/songs?page_size=${HISTORY_PAGE_SIZE}`)
		if (!res.ok) throw new Error(await readError(res))
		const { items, total } = await res.json()
		setStatus(
			historyStatusEl,
			total === 0
				? 'No songs analyzed yet.'
				: `${total} analyzed songs${total > items.length ? ` (showing the newest ${items.length})` : ''}`,
		)
		historyListEl.replaceChildren(
			...items.map(song =>
				createSongItem(
					song,
					[`score ${song.score.toFixed(2)}`, song.query, `${song.analyzed_at} UTC`].filter(Boolean).join(' · '),
				),
			),
		)
	} catch (e) {
		setStatus(historyStatusEl, `Could not load history: ${e.message}`, true)
	}
}

let scored = []

function renderResults() {
	const sorted = scored.filter(song => song.recommended).sort((a, b) => b.recommended - a.recommended)
	resultsEl.replaceChildren(
		...sorted.map(song => createSongItem(song, [song.tier, song.query].filter(Boolean).join(' · '))),
	)
}

function handleEvent(event) {
	switch (event.type) {
		case 'started':
			requestedCount = event.count
			setStatus(
				statusEl,
				event.query ? `Searching "${event.query}"...` : `Generating queries (exploration ${event.exploration}%)...`,
			)
			break
		case 'seeding':
			setStatus(statusEl, `Learning songs by ${event.artist}...`)
			break
		case 'queries':
			setStatus(statusEl, `Queries: ${event.queries.map(q => `${q.query} (${q.tier})`).join(', ')}`)
			break
		case 'downloading_model':
			setStatus(statusEl, `Downloading model ${event.model} (first run only, this may take a while)...`)
			break
		case 'fetching':
			setStatus(statusEl, 'Fetching songs...')
			break
		case 'analyzing':
			setStatus(
				statusEl,
				`Analyzing: Completed ${event.index - 1} songs; ${event.recommended_count}/${requestedCount} recommended: ${event.artist} - ${event.title}`,
			)
			break
		case 'scored':
			scored.push(event)
			renderResults()
			break
		case 'done':
			setStatus(
				statusEl,
				`Done: ${event.recommended}/${event.count} requested recommendations after analyzing ${event.analyzed} songs.`,
			)
			break
		case 'error':
			setStatus(statusEl, `Run failed: ${event.message}`, true)
			break
	}
}

function streamRun(runId) {
	const source = new EventSource(`${API_BASE}/api/runs/${runId}/events`)
	source.onmessage = message => {
		const event = JSON.parse(message.data)
		handleEvent(event)
		if (event.type === 'done' || event.type === 'error') {
			source.close()
			runButton.disabled = false
		}
	}
	// EventSource reconnects on its own and resumes from the last event id.
	source.onerror = () => {
		if (source.readyState !== EventSource.CLOSED) setStatus(statusEl, 'Connection lost, retrying...', true)
	}
}

runForm.addEventListener('submit', async submitEvent => {
	submitEvent.preventDefault()
	runButton.disabled = true
	scored = []
	renderResults()
	setStatus(statusEl, 'Waiting for the model...')
	try {
		const res = await fetch(`${API_BASE}/api/runs`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				query: runForm.query.value.trim() || null,
				count: Number(runForm.count.value),
				exploration: Number(runForm.exploration.value),
			}),
		})
		if (!res.ok) throw new Error(await readError(res))
		streamRun((await res.json()).id)
	} catch (e) {
		setStatus(statusEl, `Could not start run: ${e.message}`, true)
		runButton.disabled = false
	}
})

tasteForm.addEventListener('submit', async submitEvent => {
	submitEvent.preventDefault()
	const saveButton = tasteForm.querySelector('button')
	saveButton.disabled = true
	setStatus(tasteStatusEl, 'Saving...')
	const profile = { notes: tasteForm.notes.value }
	for (const field of LIST_FIELDS) profile[field] = parseList(tasteForm[field].value)
	try {
		const res = await fetch(`${API_BASE}/api/taste`, {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ profile }),
		})
		if (!res.ok) throw new Error(await readError(res))
		const saved = await res.json()
		fillTasteForm(saved.profile)
		const wasSetup = !hasTaste
		hasTaste = true
		tasteIntroEl.hidden = true
		setStatus(tasteStatusEl, 'Taste saved.')
		if (wasSetup) showView('run')
	} catch (e) {
		setStatus(tasteStatusEl, `Could not save taste: ${e.message}`, true)
	} finally {
		saveButton.disabled = false
	}
})

for (const button of document.querySelectorAll('nav button')) {
	button.addEventListener('click', () => showView(button.dataset.view))
}

runForm.exploration.addEventListener('input', () => {
	explorationValueEl.textContent = runForm.exploration.value
})

loadTaste()
