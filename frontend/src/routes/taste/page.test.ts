import { ApiError, type Taste } from '#lib/api.js'
import { cleanup, render, screen, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
	getTasteMock,
	saveTasteMock,
	gotoMock,
	toastSuccessMock,
	toastErrorMock,
} = vi.hoisted(() => ({
	getTasteMock: vi.fn(),
	saveTasteMock: vi.fn(),
	gotoMock: vi.fn(),
	toastSuccessMock: vi.fn(),
	toastErrorMock: vi.fn(),
}))

vi.mock('#lib/api.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/api.js')>()),
	getTaste: getTasteMock,
	saveTaste: saveTasteMock,
}))
vi.mock('$app/navigation', () => ({ goto: gotoMock }))
vi.mock('svelte-sonner', () => ({
	toast: { success: toastSuccessMock, error: toastErrorMock },
}))

import { clearTaste, saveTasteResult, taste } from '#lib/taste.svelte.js'
import Page from './+page.svelte'

const savedTaste: Taste = {
	profile: {
		liked_genres: ['Electronic'],
		liked_artists: ['Flume'],
		disliked_genres: ['Country'],
		disliked_artists: [],
		notes: 'English lyrics only.',
	},
	text: 'I like these genres: Electronic.',
	updated_at: '2026-10-10 12:00:00',
}

beforeEach(() => {
	getTasteMock.mockReset()
	saveTasteMock.mockReset()
	gotoMock.mockReset()
	toastSuccessMock.mockReset()
	toastErrorMock.mockReset()
	clearTaste()
})

afterEach(cleanup)

function getLikeGroup() {
	return screen.getByRole('group', { name: 'I like' })
}

function getSaveButton() {
	return screen.getByRole('button', { name: 'Save taste' })
}

describe('taste page', () => {
	it('shows a skeleton while the taste loads', () => {
		taste.status = 'loading'
		render(Page)

		expect(screen.getByLabelText('Loading taste')).toBeInTheDocument()
		expect(screen.queryByRole('button', { name: 'Save taste' })).toBeNull()
	})

	it('shows the error with a Retry button that reloads', async () => {
		taste.status = 'error'
		taste.error = 'Request failed (500)'
		getTasteMock.mockResolvedValue(savedTaste)
		render(Page)

		expect(screen.getByText('Request failed (500)')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

		expect(getTasteMock).toHaveBeenCalledTimes(1)
		expect(
			await screen.findByText('I like these genres: Electronic.')
		).toBeInTheDocument()
	})

	it('shows the setup intro and an empty form when no taste is saved', () => {
		render(Page)

		expect(
			screen.getByText('Tell us what you like to get started.')
		).toBeInTheDocument()
		expect(
			screen.queryByRole('heading', { name: 'What the model sees' })
		).toBeNull()
		expect(getSaveButton()).toBeDisabled()
	})

	it('fills the form from the saved profile and shows what the model sees', () => {
		saveTasteResult(savedTaste)
		render(Page)

		expect(
			screen.queryByText('Tell us what you like to get started.')
		).toBeNull()
		expect(
			within(getLikeGroup()).getByRole('button', { name: 'Remove Flume' })
		).toBeInTheDocument()
		expect(screen.getByLabelText('Anything else')).toHaveValue(
			'English lyrics only.'
		)
		expect(screen.getByText('I like these genres: Electronic.')).toBeVisible()
	})

	it('keeps Save disabled until there is a like', async () => {
		render(Page)

		await userEvent.type(screen.getByLabelText('Anything else'), 'Moody')
		expect(getSaveButton()).toBeDisabled()

		await userEvent.type(
			within(getLikeGroup()).getByLabelText('Artists'),
			'Flume{Enter}'
		)
		expect(getSaveButton()).toBeEnabled()
	})

	it('keeps Save disabled when nothing changed since the saved taste', async () => {
		saveTasteResult(savedTaste)
		render(Page)
		expect(getSaveButton()).toBeDisabled()

		await userEvent.type(screen.getByLabelText('Anything else'), '!')
		expect(getSaveButton()).toBeEnabled()

		await userEvent.type(screen.getByLabelText('Anything else'), '{Backspace}')
		expect(getSaveButton()).toBeDisabled()
	})

	it('rejects an artist already in the opposite list', async () => {
		saveTasteResult({
			...savedTaste,
			profile: { ...savedTaste.profile, disliked_artists: ['Drake'] },
		})
		render(Page)

		await userEvent.type(
			within(getLikeGroup()).getByLabelText('Artists'),
			'Drake{Enter}'
		)

		expect(screen.getByText('Already in your dislikes')).toBeInTheDocument()
	})

	it('saves the setup, then goes home with a toast', async () => {
		saveTasteMock.mockResolvedValue(savedTaste)
		render(Page)

		await userEvent.type(
			within(getLikeGroup()).getByLabelText('Artists'),
			'Flume{Enter}'
		)
		await userEvent.click(getSaveButton())

		expect(saveTasteMock).toHaveBeenCalledWith({
			liked_genres: [],
			liked_artists: ['Flume'],
			disliked_genres: [],
			disliked_artists: [],
			notes: '',
		})
		expect(toastSuccessMock).toHaveBeenCalledWith('Taste saved')
		expect(gotoMock).toHaveBeenCalledWith('/')
		expect(taste.status).toBe('ready')
	})

	it('stays on the page after editing and refreshes what the model sees', async () => {
		saveTasteResult(savedTaste)
		saveTasteMock.mockResolvedValue({
			...savedTaste,
			text: 'Updated text.',
			profile: { ...savedTaste.profile, notes: 'Moody' },
		})
		render(Page)

		const notes = screen.getByLabelText('Anything else')
		await userEvent.clear(notes)
		await userEvent.type(notes, 'Moody')
		await userEvent.click(getSaveButton())

		expect(await screen.findByText('Updated text.')).toBeInTheDocument()
		expect(toastSuccessMock).toHaveBeenCalledWith('Taste saved')
		expect(gotoMock).not.toHaveBeenCalled()
		expect(getSaveButton()).toBeDisabled()
	})

	it('shows a 422 message inline without a toast', async () => {
		saveTasteMock.mockRejectedValue(
			new ApiError('Add at least one liked genre or artist', 422)
		)
		render(Page)

		await userEvent.type(
			within(getLikeGroup()).getByLabelText('Artists'),
			'Flume{Enter}'
		)
		await userEvent.click(getSaveButton())

		expect(await screen.findByRole('alert')).toHaveTextContent(
			'Add at least one liked genre or artist'
		)
		expect(toastErrorMock).not.toHaveBeenCalled()
		expect(gotoMock).not.toHaveBeenCalled()
	})

	it('shows a toast for other failures', async () => {
		saveTasteMock.mockRejectedValue(new ApiError('Request failed (500)', 500))
		render(Page)

		await userEvent.type(
			within(getLikeGroup()).getByLabelText('Artists'),
			'Flume{Enter}'
		)
		await userEvent.click(getSaveButton())

		await vi.waitFor(() =>
			expect(toastErrorMock).toHaveBeenCalledWith('Request failed (500)')
		)
		expect(screen.queryByRole('alert')).toBeNull()
	})
})
