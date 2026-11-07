import type { ModelStatus, Taste } from '#lib/api.js'
import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
	startNewRunMock,
	playSongMock,
	watchModelCacheMock,
	downloadMissingModelsMock,
	getTasteMock,
	saveTasteMock,
} = vi.hoisted(() => ({
	startNewRunMock: vi.fn(),
	playSongMock: vi.fn(),
	watchModelCacheMock: vi.fn(),
	downloadMissingModelsMock: vi.fn(),
	getTasteMock: vi.fn(),
	saveTasteMock: vi.fn(),
}))

vi.mock('#lib/api.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/api.js')>()),
	getTaste: getTasteMock,
	saveTaste: saveTasteMock,
}))

vi.mock('#lib/modelCache.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/modelCache.svelte.js')>()),
	watchModelCache: watchModelCacheMock,
	downloadMissingModels: downloadMissingModelsMock,
}))

vi.mock('#lib/player.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/player.svelte.js')>()),
	playSong: playSongMock,
}))

vi.mock('#lib/run.svelte.js', () => ({
	run: {
		phase: 'idle',
		status: '',
		count: 0,
		recommended: 0,
		cards: [],
		error: null,
	},
	startNewRun: startNewRunMock,
	RUN_QUEUE_ORIGIN: 'run',
}))

import { modelCache } from '#lib/modelCache.svelte.js'
import { run } from '#lib/run.svelte.js'
import { clearTaste, saveTasteResult, taste } from '#lib/taste.svelte.js'
import Page from './+page.svelte'

const savedTaste: Taste = {
	profile: {
		liked_genres: [],
		liked_artists: ['Flume'],
		disliked_genres: [],
		disliked_artists: [],
		notes: '',
	},
	text: 'I like Flume.',
	updated_at: '2026-10-10 12:00:00',
}

function makeModel(
	id: string,
	overrides: Partial<ModelStatus> = {}
): ModelStatus {
	return {
		id,
		downloaded: false,
		size_bytes: 2_000_000_000,
		download: null,
		...overrides,
	}
}

function makeActiveDownload(
	state: 'pending' | 'downloading',
	downloadedBytes: number
): NonNullable<ModelStatus['download']> {
	return {
		state,
		downloaded_bytes: downloadedBytes,
		total_bytes: 100,
		bytes_per_second: 10,
		seconds_remaining: downloadedBytes === 0 ? null : 5,
		error: null,
	}
}

beforeEach(() => {
	run.phase = 'idle'
	run.status = ''
	run.cards = []
	startNewRunMock.mockReset()
	playSongMock.mockReset()
	downloadMissingModelsMock.mockReset()
	getTasteMock.mockReset()
	saveTasteMock.mockReset()
	watchModelCacheMock.mockReset().mockReturnValue(() => {})
	saveTasteResult(savedTaste)
	modelCache.status = 'ready'
	modelCache.items = [
		makeModel('org/first', { downloaded: true }),
		makeModel('org/second', { downloaded: true }),
	]
})

afterEach(() => {
	cleanup()
	clearTaste()
	// An open dialog locks the body and unmounting does not always release it.
	document.body.style.removeProperty('pointer-events')
})

describe('home page', () => {
	it('shows the heading and description', () => {
		render(Page)

		expect(
			screen.getByRole('heading', { name: 'Discover something new' })
		).toBeInTheDocument()
		expect(
			screen.getByText("Based on your taste, I'll find music you might like")
		).toBeInTheDocument()
	})

	it('defaults the song count to 3 and starts a run with it', async () => {
		render(Page)
		await userEvent.click(screen.getByRole('button', { name: 'Settings' }))
		expect(screen.getByText('Songs:')).toBeInTheDocument()
		expect(screen.getByLabelText('Songs to find')).toHaveTextContent('3')
		await userEvent.click(
			screen.getByRole('button', { name: 'Find new music' })
		)

		expect(startNewRunMock).toHaveBeenCalledWith(3, 50)
	})

	it('starts a run with the chosen exploration', async () => {
		render(Page)
		await userEvent.click(screen.getByRole('button', { name: 'Settings' }))
		expect(screen.getByLabelText('Exploration level')).toHaveTextContent('50%')
		await fireEvent.keyDown(screen.getByRole('slider', { hidden: true }), {
			key: 'ArrowRight',
		})
		await waitFor(() =>
			expect(screen.getByLabelText('Exploration level')).toHaveTextContent(
				'51%'
			)
		)
		await userEvent.click(
			screen.getByRole('button', { name: 'Find new music' })
		)

		expect(startNewRunMock).toHaveBeenCalledWith(3, 51)
	})

	it('hides the stepper until settings is opened', () => {
		render(Page)

		expect(screen.queryByLabelText('Songs to find')).not.toBeInTheDocument()
	})

	it('starts a run with the stepped count', async () => {
		render(Page)
		await userEvent.click(screen.getByRole('button', { name: 'Settings' }))
		await userEvent.click(screen.getByLabelText('More songs'))
		await userEvent.click(screen.getByLabelText('More songs'))
		await userEvent.click(screen.getByLabelText('Fewer songs'))
		expect(screen.getByLabelText('Songs to find')).toHaveTextContent('4')
		await userEvent.click(
			screen.getByRole('button', { name: 'Find new music' })
		)

		expect(startNewRunMock).toHaveBeenCalledWith(4, 50)
	})

	it('stops the stepper at 1', async () => {
		render(Page)
		await userEvent.click(screen.getByRole('button', { name: 'Settings' }))
		const fewer = screen.getByLabelText('Fewer songs')
		await userEvent.click(fewer)
		await userEvent.click(fewer)

		expect(screen.getByLabelText('Songs to find')).toHaveTextContent('1')
		expect(fewer).toBeDisabled()
	})

	it('disables the controls while a run is active', async () => {
		run.phase = 'preparing'
		render(Page)
		await userEvent.click(screen.getByRole('button', { name: 'Settings' }))

		expect(
			screen.getByRole('button', { name: 'Finding music...' })
		).toBeDisabled()
		expect(screen.getByLabelText('Fewer songs')).toBeDisabled()
		expect(screen.getByLabelText('More songs')).toBeDisabled()
	})

	it('shows the status text', () => {
		run.phase = 'preparing'
		run.status = 'Searching...'
		render(Page)

		expect(screen.getByText('Searching...')).toBeInTheDocument()
	})

	it('shows every model download at once with its state', () => {
		run.phase = 'preparing'
		modelCache.items = [
			makeModel('org/first', {
				download: makeActiveDownload('downloading', 50),
			}),
			makeModel('org/second', {
				download: makeActiveDownload('pending', 0),
			}),
		]
		render(Page)

		expect(
			screen.getByRole('progressbar', { name: 'Downloading org/first' })
		).toHaveAttribute('aria-valuenow', '50')
		expect(
			screen.getByRole('progressbar', {
				name: 'Waiting to download org/second',
			})
		).toHaveAttribute('aria-valuenow', '0')
	})

	it('shows a download started elsewhere even when no run is active', () => {
		modelCache.items = [
			makeModel('org/first', {
				download: makeActiveDownload('downloading', 50),
			}),
			makeModel('org/second', { downloaded: true }),
		]
		render(Page)

		expect(
			screen.getByRole('progressbar', { name: 'Downloading org/first' })
		).toBeInTheDocument()
	})

	it('watches the models while mounted and stops on unmount', () => {
		const stopWatching = vi.fn()
		watchModelCacheMock.mockReturnValue(stopWatching)
		const { unmount } = render(Page)

		expect(watchModelCacheMock).toHaveBeenCalledOnce()
		unmount()
		expect(stopWatching).toHaveBeenCalledOnce()
	})

	it('hides the model download panels without downloads', () => {
		run.phase = 'preparing'
		render(Page)

		expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
	})

	it('shows the first loading card while preparing', () => {
		run.phase = 'preparing'
		run.cards = [{ kind: 'loading', video_id: 'a', title: 'A', artist: 'B' }]
		render(Page)

		expect(screen.getByText('Recommended for you')).toBeInTheDocument()
		expect(screen.getByLabelText('Analyzing A')).toHaveAttribute(
			'aria-busy',
			'true'
		)
	})

	it('shows recommendations and loading cards while streaming', () => {
		run.phase = 'streaming'
		run.cards = [
			{
				kind: 'song',
				song: {
					video_id: 'a',
					title: 'Song A',
					artist: 'Artist A',
					url: 'https://youtu.be/a',
					recommended: true,
					confidence: 0.87,
					query: null,
				},
			},
			{ kind: 'loading', video_id: 'b', title: 'Song B', artist: 'Artist B' },
		]
		render(Page)

		expect(screen.getByText('Recommended for you')).toBeInTheDocument()
		expect(screen.getByText('Song A')).toBeInTheDocument()
		expect(screen.getByText('87%')).toBeInTheDocument()
		expect(screen.getByLabelText('Analyzing Song B')).toHaveAttribute(
			'aria-busy',
			'true'
		)
	})

	it('shows a Play All button that plays the first song', async () => {
		const makeSong = (id: string) => ({
			video_id: id,
			title: `Song ${id}`,
			artist: 'Artist',
			url: `https://youtu.be/${id}`,
			recommended: true,
			confidence: 0.9,
			query: null,
		})
		run.phase = 'done'
		run.status = 'Done'
		run.cards = [
			{ kind: 'song', song: makeSong('a') },
			{ kind: 'song', song: makeSong('b') },
		]
		render(Page)

		expect(screen.getByText('Done')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Play All' }))

		expect(playSongMock).toHaveBeenCalledWith(
			expect.objectContaining({ video_id: 'a' }),
			[
				expect.objectContaining({ video_id: 'a' }),
				expect.objectContaining({ video_id: 'b' }),
			],
			'run'
		)
	})

	it('shows the Play All button as soon as one song is ready while others load', () => {
		run.phase = 'streaming'
		run.cards = [
			{
				kind: 'song',
				song: {
					video_id: 'a',
					title: 'Song A',
					artist: 'Artist A',
					url: 'https://youtu.be/a',
					recommended: true,
					confidence: 0.9,
					query: null,
				},
			},
			{ kind: 'loading', video_id: 'b', title: 'Song B', artist: 'Artist B' },
		]
		render(Page)

		expect(screen.getByRole('button', { name: 'Play All' })).toBeInTheDocument()
	})

	it('hides the Play All button when there are no songs yet', () => {
		run.phase = 'preparing'
		run.cards = [{ kind: 'loading', video_id: 'a', title: 'A', artist: 'B' }]
		render(Page)

		expect(
			screen.queryByRole('button', { name: 'Play All' })
		).not.toBeInTheDocument()
	})

	it('shows the empty state when a run finishes with no recommendations', () => {
		run.phase = 'done'
		render(Page)

		expect(
			screen.getByText(
				'No new recommendations this time. Try again for a fresh batch.'
			)
		).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Find new music' })).toBeEnabled()
	})
})

describe('first-run taste flow', () => {
	function setMissingModels() {
		modelCache.items = [makeModel('org/first'), makeModel('org/second')]
	}

	async function saveTasteInModal() {
		const likes = screen.getByRole('group', { name: 'I like' })
		await userEvent.type(
			within(likes).getByLabelText('Artists'),
			'Flume{Enter}'
		)
		await userEvent.click(screen.getByRole('button', { name: 'Save' }))
	}

	it('shows a skeleton while the taste loads', () => {
		taste.status = 'loading'
		render(Page)

		expect(screen.getByLabelText('Loading taste')).toBeInTheDocument()
		expect(
			screen.queryByRole('button', { name: 'Find new music' })
		).not.toBeInTheDocument()
	})

	it('shows the error with a Retry button that reloads the taste', async () => {
		taste.status = 'error'
		taste.error = 'Request failed (500)'
		getTasteMock.mockResolvedValue(savedTaste)
		render(Page)

		expect(screen.getByText('Request failed (500)')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

		expect(
			await screen.findByRole('button', { name: 'Find new music' })
		).toBeInTheDocument()
	})

	it('asks for a taste instead of offering to find music', () => {
		clearTaste()
		setMissingModels()
		render(Page)

		expect(
			screen.getByRole('button', { name: 'What music do you like?' })
		).toBeInTheDocument()
		expect(
			screen.queryByRole('button', { name: 'Find new music' })
		).not.toBeInTheDocument()
	})

	it('opens the taste modal without starting a download', async () => {
		clearTaste()
		setMissingModels()
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)

		expect(await screen.findByRole('dialog')).toBeInTheDocument()
		expect(
			screen.getByRole('button', { name: 'Download Models' })
		).toBeInTheDocument()
		expect(screen.getByText(/About 4\.0 GB/)).toBeInTheDocument()
		expect(downloadMissingModelsMock).not.toHaveBeenCalled()
	})

	it('hides the model section in the modal when the models are downloaded', async () => {
		clearTaste()
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)

		await screen.findByRole('dialog')
		expect(
			screen.queryByRole('button', { name: 'Download Models' })
		).not.toBeInTheDocument()
	})

	it('shows the download progress in the modal while models download', async () => {
		clearTaste()
		modelCache.items = [
			makeModel('org/first', {
				download: makeActiveDownload('downloading', 42),
			}),
			makeModel('org/second', { download: makeActiveDownload('pending', 0) }),
		]
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)

		expect(await screen.findByText('Downloading models...')).toBeInTheDocument()
		expect(
			screen.queryByRole('button', { name: 'Download Models' })
		).not.toBeInTheDocument()
		expect(
			screen.getByText(
				'You can continue entering your preferences while they download.'
			)
		).toBeInTheDocument()
	})

	it('starts the downloads only when Download Models is clicked', async () => {
		clearTaste()
		setMissingModels()
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)
		await userEvent.click(
			await screen.findByRole('button', { name: 'Download Models' })
		)

		expect(downloadMissingModelsMock).toHaveBeenCalledOnce()
	})

	it('closes the modal on save and follows the download until the models are ready', async () => {
		clearTaste()
		setMissingModels()
		saveTasteMock.mockResolvedValue(savedTaste)
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)
		await screen.findByRole('dialog')
		modelCache.items = [
			makeModel('org/first', {
				download: makeActiveDownload('downloading', 72),
			}),
			makeModel('org/second', { download: makeActiveDownload('pending', 0) }),
		]
		await saveTasteInModal()

		await waitFor(() =>
			expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
		)
		expect(
			screen.getByText('Your taste is saved. Models are still downloading...')
		).toBeInTheDocument()
		expect(
			screen.getByRole('button', { name: 'Getting ready...' })
		).toBeDisabled()
		expect(startNewRunMock).not.toHaveBeenCalled()

		modelCache.items = [
			makeModel('org/first', { downloaded: true }),
			makeModel('org/second', { downloaded: true }),
		]

		expect(await screen.findByText('Your taste is ready.')).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Find new music' })).toBeEnabled()
		expect(startNewRunMock).not.toHaveBeenCalled()
	})

	it('goes straight to Find new music after saving when the models are downloaded', async () => {
		clearTaste()
		saveTasteMock.mockResolvedValue(savedTaste)
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'What music do you like?' })
		)
		await screen.findByRole('dialog')
		await saveTasteInModal()

		expect(
			await screen.findByRole('button', { name: 'Find new music' })
		).toBeEnabled()
		expect(screen.queryByText('Your taste is ready.')).not.toBeInTheDocument()
	})

	it('keeps the normal flow for a taste with models still missing', async () => {
		setMissingModels()
		render(Page)

		await userEvent.click(
			screen.getByRole('button', { name: 'Find new music' })
		)

		expect(startNewRunMock).toHaveBeenCalledWith(3, 50)
		expect(
			screen.queryByText('Your taste is saved. Models are still downloading...')
		).not.toBeInTheDocument()
	})
})
