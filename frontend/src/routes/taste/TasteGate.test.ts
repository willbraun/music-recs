import type { Taste } from '#lib/api.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { createRawSnippet } from 'svelte'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { getTasteMock, gotoMock, pageMock } = vi.hoisted(() => ({
	getTasteMock: vi.fn(),
	gotoMock: vi.fn(),
	pageMock: { url: { pathname: '/' } },
}))

vi.mock('#lib/api.js', () => ({ getTaste: getTasteMock }))
vi.mock('$app/navigation', () => ({ goto: gotoMock }))
vi.mock('$app/state', () => ({ page: pageMock }))

import { clearTaste, taste } from '#lib/taste.svelte.js'
import TasteGate from './TasteGate.svelte'

const savedTaste: Taste = {
	profile: {
		liked_genres: ['Electronic'],
		liked_artists: [],
		disliked_genres: [],
		disliked_artists: [],
		notes: '',
	},
	text: 'I like these genres: Electronic.',
	updated_at: '2026-10-10 12:00:00',
}

const children = createRawSnippet(() => ({
	render: () => '<p>Page content</p>',
}))

beforeEach(() => {
	getTasteMock.mockReset()
	gotoMock.mockReset()
	pageMock.url.pathname = '/'
	clearTaste()
	taste.status = 'loading'
})

afterEach(cleanup)

describe('TasteGate', () => {
	it('hides the page while the taste loads', () => {
		getTasteMock.mockReturnValue(new Promise(() => {}))
		render(TasteGate, { children })

		expect(screen.queryByText('Page content')).toBeNull()
		expect(gotoMock).not.toHaveBeenCalled()
	})

	it('shows the page once a taste is loaded', async () => {
		getTasteMock.mockResolvedValue(savedTaste)
		render(TasteGate, { children })

		expect(await screen.findByText('Page content')).toBeInTheDocument()
		expect(gotoMock).not.toHaveBeenCalled()
	})

	it('redirects to /taste when there is no taste', async () => {
		getTasteMock.mockResolvedValue(null)
		render(TasteGate, { children })

		await vi.waitFor(() =>
			expect(gotoMock).toHaveBeenCalledWith('/taste', { replaceState: true })
		)
		expect(screen.queryByText('Page content')).toBeNull()
	})

	it('keeps the taste page without a taste and does not redirect', async () => {
		pageMock.url.pathname = '/taste'
		getTasteMock.mockResolvedValue(null)
		render(TasteGate, { children })

		expect(await screen.findByText('Page content')).toBeInTheDocument()
		await vi.waitFor(() => expect(taste.status).toBe('none'))
		expect(gotoMock).not.toHaveBeenCalled()
	})

	it('shows an error with Retry when the taste cannot be loaded', async () => {
		getTasteMock.mockRejectedValueOnce(new Error('Request failed (500)'))
		getTasteMock.mockResolvedValueOnce(savedTaste)
		render(TasteGate, { children })

		expect(await screen.findByText('Request failed (500)')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

		expect(await screen.findByText('Page content')).toBeInTheDocument()
	})
})
