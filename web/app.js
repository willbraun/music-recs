const API_BASE = window.API_BASE ?? ''
const YOUTUBE_PREFIX = 'https://www.youtube.com/'

const runForm = document.getElementById('run-form')
const runButton = runForm.querySelector('button')
const explorationValueEl = document.getElementById('exploration-value')
const statusEl = document.getElementById('status')
const resultsEl = document.getElementById('results')
const historyStatusEl = document.getElementById('history-status')
const historyListEl = document.getElementById('history-list')
let requestedCount = 0

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
		createElement('details', {}, createElement('summary', {}, 'Description'), createElement('p', {}, song.description)),
	)
}

function showView(name) {
	for (const button of document.querySelectorAll('nav button')) {
		button.classList.toggle('active', button.dataset.view === name)
	}
	for (const section of document.querySelectorAll('main > section')) {
		section.hidden = section.id !== name
	}
	if (name === 'history') loadHistory()
}

async function loadHistory() {
	setStatus(historyStatusEl, 'Loading...')
	try {
		const res = await fetch(`${API_BASE}/api/songs`)
		if (!res.ok) throw new Error(`Request failed (${res.status})`)
		const songs = await res.json()
		setStatus(historyStatusEl, songs.length ? `${songs.length} analyzed songs` : 'No songs analyzed yet.')
		historyListEl.replaceChildren(
			...songs.map(song => {
				const taste = song.taste_version == null ? null : `taste v${song.taste_version}`
				return createSongItem(song, [song.query, taste, `${song.analyzed_at} UTC`].filter(Boolean).join(' · '))
			}),
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
				event.query
					? `Searching "${event.query}" (taste v${event.taste_version})...`
					: `Generating queries (exploration ${event.exploration}%, taste v${event.taste_version})...`,
			)
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
		if (!res.ok) throw new Error(`Request failed (${res.status})`)
		streamRun((await res.json()).id)
	} catch (e) {
		setStatus(statusEl, `Could not start run: ${e.message}`, true)
		runButton.disabled = false
	}
})

for (const button of document.querySelectorAll('nav button')) {
	button.addEventListener('click', () => showView(button.dataset.view))
}

runForm.exploration.addEventListener('input', () => {
	explorationValueEl.textContent = runForm.exploration.value
})
