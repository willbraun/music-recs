import { cleanup, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { pageMock } = vi.hoisted(() => ({
	pageMock: { url: { pathname: '/' } },
}))

vi.mock('$app/state', () => ({ page: pageMock }))

import { update } from '#lib/update.svelte.js'
import Header from './Header.svelte'

afterEach(() => {
	cleanup()
	update.latestVersion = null
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
})
