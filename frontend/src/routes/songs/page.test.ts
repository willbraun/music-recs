import type { Song } from '#lib/api.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { listSongsMock, playSongMock } = vi.hoisted(() => ({
	listSongsMock: vi.fn(),
	playSongMock: vi.fn(),
}))

vi.mock('#lib/api.js', () => ({ listSongs: listSongsMock }))
vi.mock('#lib/player.svelte.js', () => ({
	player: { current: null, status: 'idle' },
	playSong: playSongMock,
}))

import Page from './+page.svelte'

const songs: Song[] = [
	{
		video_id: 'a',
		title: 'First Song',
		artist: 'Artist A',
		album: 'Album A',
		url: 'https://www.youtube.com/watch?v=a',
		recommended: true,
		confidence: 0.87,
		query: null,
	},
	{
		video_id: 'b',
		title: 'Second Song',
		artist: 'Artist B',
		album: null,
		url: 'https://www.youtube.com/watch?v=b',
		recommended: false,
		confidence: 0.64,
		query: null,
	},
]

beforeEach(() => {
	listSongsMock.mockReset()
	playSongMock.mockReset()
})

afterEach(cleanup)

function makePage(items: Song[], total = items.length, page = 1) {
	return { items, total, page, page_size: 50 }
}

describe('songs page', () => {
	it('lists every song with a single match score', async () => {
		listSongsMock.mockResolvedValue(makePage(songs))
		render(Page)

		expect(await screen.findByText('First Song')).toBeInTheDocument()
		expect(screen.getByText('Second Song')).toBeInTheDocument()
		expect(screen.getByText('Album A')).toBeInTheDocument()
		expect(screen.getByTitle('Recommended')).toHaveTextContent('87%')
		expect(screen.getByTitle('Not recommended')).toHaveTextContent('36%')
		expect(screen.getByText('1-2 of 2')).toBeInTheDocument()
	})

	it('plays the clicked song with the list as the queue', async () => {
		listSongsMock.mockResolvedValue(makePage(songs))
		render(Page)

		await userEvent.click(
			await screen.findByRole('button', {
				name: 'Play Second Song by Artist B',
			})
		)

		expect(playSongMock).toHaveBeenCalledWith(songs[1], songs, 'songs')
	})

	it('shows an empty state', async () => {
		listSongsMock.mockResolvedValue(makePage([]))
		render(Page)

		expect(await screen.findByText(/No songs yet/)).toBeInTheDocument()
	})

	it('hides the page arrows when everything fits on one page', async () => {
		listSongsMock.mockResolvedValue(makePage(songs))
		render(Page)

		await screen.findByText('First Song')
		expect(screen.queryByRole('button', { name: 'Next page' })).toBeNull()
	})

	it('moves between pages with the arrows', async () => {
		listSongsMock.mockResolvedValueOnce(makePage([songs[0]], 60, 1))
		listSongsMock.mockResolvedValueOnce(makePage([songs[1]], 60, 2))
		vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
		render(Page)

		expect(await screen.findByText('First Song')).toBeInTheDocument()
		expect(screen.getByText('1-1 of 60')).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()

		await userEvent.click(screen.getByRole('button', { name: 'Next page' }))

		expect(await screen.findByText('Second Song')).toBeInTheDocument()
		expect(screen.getByText('51-51 of 60')).toBeInTheDocument()
		expect(listSongsMock).toHaveBeenLastCalledWith(2)
		expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled()
		expect(screen.getByRole('button', { name: 'Previous page' })).toBeEnabled()
	})

	it('shows an error with a retry button', async () => {
		listSongsMock.mockRejectedValueOnce(new Error('Boom'))
		listSongsMock.mockResolvedValueOnce(makePage(songs))
		render(Page)

		expect(await screen.findByText('Boom')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
		expect(await screen.findByText('First Song')).toBeInTheDocument()
	})
})
