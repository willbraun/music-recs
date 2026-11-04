import { cleanup, render, screen, within } from '@testing-library/svelte'
import { afterEach, describe, expect, it } from 'vitest'
import Page from './+page.svelte'

afterEach(cleanup)

describe('about page', () => {
	it('describes what the app does and how it works', () => {
		render(Page)

		expect(
			screen.getByRole('heading', { name: 'About', level: 1 })
		).toBeInTheDocument()
		expect(
			screen.getByText(/recommends songs based on your musical taste/)
		).toBeInTheDocument()
		const steps = within(
			screen.getByRole('region', { name: 'How It Works' })
		).getAllByRole('listitem')
		expect(steps.length).toBeGreaterThan(0)
	})

	it('lists the system requirements', () => {
		render(Page)
		const section = screen.getByRole('region', { name: 'System Requirements' })

		for (const term of [
			'Disk Space',
			'Memory (VRAM)',
			'Processor',
			'Operating System',
			'Internet',
		]) {
			expect(within(section).getByText(term)).toBeInTheDocument()
		}
	})
})
