import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { startNewRunMock, playSongMock } = vi.hoisted(() => ({
	startNewRunMock: vi.fn(),
	playSongMock: vi.fn(),
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

import { run } from '#lib/run.svelte.js'
import Page from './+page.svelte'

beforeEach(() => {
	run.phase = 'idle'
	run.status = ''
	run.cards = []
	startNewRunMock.mockReset()
	playSongMock.mockReset()
})

afterEach(cleanup)

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
