import { MODELS } from '#lib/models.js'
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

	it('links each model to its license page', () => {
		render(Page)
		const section = screen.getByRole('region', { name: 'Model Licenses' })

		for (const model of MODELS) {
			expect(
				within(section).getByRole('link', {
					name: `${model.license.name} for ${model.name}`,
				})
			).toHaveAttribute('href', model.license.path)
		}
	})

	it('offers View Original for Qwen and Download Original for NVIDIA', () => {
		render(Page)
		const section = screen.getByRole('region', { name: 'Model Licenses' })

		const view = within(section).getByRole('link', { name: /View original/ })
		expect(view).toHaveTextContent('View Original')
		expect(view).toHaveAttribute('href', MODELS[0].license.original.url)
		expect(view).not.toHaveAttribute('download')

		const download = within(section).getByRole('link', {
			name: /Download original/,
		})
		expect(download).toHaveTextContent('Download Original')
		expect(download).toHaveAttribute('href', MODELS[1].license.original.url)
		expect(download).toHaveAttribute('download')
	})

	it('shows the use limits for each model and the app-wide message', () => {
		render(Page)

		expect(
			screen.getByText(/Licensed for research or evaluation only/)
		).toBeInTheDocument()
		expect(
			screen.getByText(/Licensed for academic, non-commercial use only/)
		).toBeInTheDocument()
		expect(
			screen.getByText(/limits it to academic purposes/)
		).toBeInTheDocument()
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
