import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { gotoMock } = vi.hoisted(() => ({ gotoMock: vi.fn() }))

vi.mock('$app/navigation', () => ({ goto: gotoMock }))

import { profiles } from '#lib/profiles.svelte.js'
import Page from './+page.svelte'

afterEach(() => {
	cleanup()
	profiles.status = 'loading'
	profiles.items = []
	profiles.activeId = null
	profiles.error = null
	sessionStorage.clear()
	gotoMock.mockReset()
})

describe('profile picker', () => {
	it('shows a loading state until the profiles arrive', () => {
		render(Page)

		expect(screen.getByLabelText('Loading profiles')).toBeInTheDocument()
	})

	it('lists every profile and links to add another', () => {
		profiles.status = 'ready'
		profiles.items = [
			{ id: 1, name: 'Ann', avatar: '🎸' },
			{ id: 2, name: 'Bob', avatar: '🎹' },
		]
		render(Page)

		expect(screen.getByRole('button', { name: 'Ann' })).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Bob' })).toBeInTheDocument()
		expect(screen.getByRole('link', { name: 'Add profile' })).toHaveAttribute(
			'href',
			'/add-profile'
		)
	})

	it('opens the app as the chosen profile', async () => {
		profiles.status = 'ready'
		profiles.items = [{ id: 2, name: 'Bob', avatar: '🎹' }]
		render(Page)

		await userEvent.click(screen.getByRole('button', { name: 'Bob' }))

		expect(profiles.activeId).toBe(2)
		expect(gotoMock).toHaveBeenCalledWith('/')
	})

	it('offers a retry when the profiles could not be loaded', () => {
		profiles.status = 'error'
		profiles.error = 'Down'
		render(Page)

		expect(screen.getByText('Down')).toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
	})
})
