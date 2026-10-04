const API_BASE = window.API_BASE ?? ''
const YOUTUBE_PREFIX = 'https://www.youtube.com/'

const runForm = document.getElementById('run-form')
const runButton = runForm.querySelector('button')
const statusEl = document.getElementById('status')
const resultsEl = document.getElementById('results')
const historyStatusEl = document.getElementById('history-status')
const historyListEl = document.getElementById('history-list')

// Text goes in via textContent only: titles and descriptions come from YouTube and a model.
function el(tag, props = {}, ...children) {
	const node = Object.assign(document.createElement(tag), props)
	node.append(...children)
	return node
}

function setStatus(node, text, isError = false) {
	node.textContent = text
	node.className = isError ? 'error' : ''
}

function songLink(song) {
	const label = `${song.artist} - ${song.title}`
	if (!song.url.startsWith(YOUTUBE_PREFIX)) return el('span', {}, label)
	return el('a', { href: song.url, target: '_blank', rel: 'noopener' }, label)
}

function songItem(song, meta = '') {
	return el(
		'li',
		{ className: song.recommended ? 'recommended' : '' },
		songLink(song),
		el('span', { className: 'meta' }, meta),
		el('details', {}, el('summary', {}, 'Description'), el('p', {}, song.description)),
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
				return songItem(song, [song.query, taste, `${song.analyzed_at} UTC`].filter(Boolean).join(' · '))
			}),
		)
	} catch (e) {
		setStatus(historyStatusEl, `Could not load history: ${e.message}`, true)
	}
}

let scored = []

function renderResults() {
	const sorted = [...scored].sort((a, b) => b.recommended - a.recommended)
	resultsEl.replaceChildren(...sorted.map(song => songItem(song)))
}

function handleEvent(event) {
	switch (event.type) {
		case 'started':
			setStatus(statusEl, `Searching "${event.query}" (taste v${event.taste_version})...`)
			break
		case 'analyzing':
			setStatus(statusEl, `Analyzing ${event.index}/${runForm.count.value}: ${event.artist} - ${event.title}`)
			break
		case 'scored':
			scored.push(event)
			renderResults()
			break
		case 'done':
			setStatus(statusEl, `Done: ${event.recommended} recommended of ${event.analyzed} new tracks.`)
			break
		case 'error':
			setStatus(statusEl, `Run failed: ${event.message}`, true)
			break
	}
}

function stream(runId) {
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
				query: runForm.query.value,
				count: Number(runForm.count.value),
			}),
		})
		if (!res.ok) throw new Error(`Request failed (${res.status})`)
		stream((await res.json()).id)
	} catch (e) {
		setStatus(statusEl, `Could not start run: ${e.message}`, true)
		runButton.disabled = false
	}
})

for (const button of document.querySelectorAll('nav button')) {
	button.addEventListener('click', () => showView(button.dataset.view))
}
