import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { pageMock } = vi.hoisted(() => ({
	pageMock: { url: { pathname: '/' } },
}))

const { gotoMock } = vi.hoisted(() => ({ gotoMock: vi.fn() }))

vi.mock('$app/state', () => ({ page: pageMock }))
vi.mock('$app/navigation', () => ({ goto: gotoMock }))

import { profiles } from '#lib/profiles.svelte.js'
import { update } from '#lib/update.svelte.js'
import Header from './Header.svelte'

afterEach(() => {
	cleanup()
	update.latestVersion = null
	profiles.items = []
	profiles.activeId = null
	sessionStorage.clear()
	document.body.style.pointerEvents = ''
	gotoMock.mockReset()
})

describe('Header', () => {
	it('links the brand and every page from the main navigation', () => {
		render(Header)
		const nav = screen.getByRole('navigation', { name: 'Main' })

		expect(nav).toContainElement(
			screen.getByRole('link', { name: 'Music Recs' })
		)
		expect(screen.getByRole('link', { name: 'Music Recs' })).toHaveAttribute(
			'href',
			'/'
		)
		expect(screen.getByRole('link', { name: 'Discover' })).toHaveAttribute(
			'href',
			'/'
		)
		expect(screen.getByRole('link', { name: 'Songs' })).toHaveAttribute(
			'href',
			'/songs'
		)
		expect(screen.getByRole('link', { name: 'Taste' })).toHaveAttribute(
			'href',
			'/taste'
		)
		expect(screen.getByRole('link', { name: 'Models' })).toHaveAttribute(
			'href',
			'/models'
		)
		expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute(
			'href',
			'/about'
		)
	})

	it.each([
		['/', 'Discover'],
		['/songs', 'Songs'],
		['/taste', 'Taste'],
		['/models', 'Models'],
		['/about', 'About'],
	])('marks only the current page at %s', (pathname, label) => {
		pageMock.url.pathname = pathname
		render(Header)

		const current = screen.getAllByRole('link', { current: 'page' })
		expect(current).toHaveLength(1)
		expect(current[0]).toHaveTextContent(label)
	})

	it('marks no page as current on an unknown route', () => {
		pageMock.url.pathname = '/elsewhere'
		render(Header)

		expect(screen.queryByRole('link', { current: 'page' })).toBeNull()
	})

	it('offers no update button by default', () => {
		render(Header)

		expect(
			screen.queryByRole('link', { name: 'New Version Available' })
		).toBeNull()
	})

	it('links to the latest release when a new version is available', () => {
		update.latestVersion = '0.2.0'
		render(Header)

		const button = screen.getByRole('link', { name: 'New Version Available' })
		expect(button).toHaveAttribute(
			'href',
			'https://github.com/willbraun/music-recs/releases/latest'
		)
		expect(button).toHaveAttribute('target', '_blank')
		expect(button).toHaveAttribute('title', 'Version 0.2.0 is available')
	})

	describe('profile menu', () => {
		const ANN = { id: 1, name: 'Ann', avatar: '🎸' }
		const BOB = { id: 2, name: 'Bob', avatar: '🎹' }

		function signIn() {
			profiles.items = [ANN, BOB]
			profiles.activeId = 1
		}

		it('is absent until a profile is chosen', () => {
			render(Header)

			expect(screen.queryByRole('button', { name: /Profile menu/ })).toBeNull()
		})

		// jsdom never positions the popover, so it stays visibility:hidden and has no accessible name.
		function getMenuItem(text: string) {
			return screen.getByText(text).closest('[role="menuitem"]')
		}

		it('lists the other profiles, then manage and add links', async () => {
			signIn()
			render(Header)

			await userEvent.click(
				screen.getByRole('button', { name: 'Profile menu, Ann' })
			)

			expect(await screen.findByText('Bob')).toBeInTheDocument()
			expect(screen.queryByText('Ann')).toBeNull()
			expect(getMenuItem('Manage profile')).toHaveAttribute(
				'href',
				'/profile/1'
			)
			expect(getMenuItem('Add profile')).toHaveAttribute('href', '/add-profile')
		})

		it('switches to the chosen profile and returns to Discover', async () => {
			signIn()
			render(Header)

			await userEvent.click(
				screen.getByRole('button', { name: 'Profile menu, Ann' })
			)
			await userEvent.click((await screen.findByText('Bob')) as HTMLElement)

			expect(profiles.activeId).toBe(2)
			expect(gotoMock).toHaveBeenCalledWith('/')
		})
	})
})
