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
			'Memory',
			'Processor',
			'Operating System',
			'Internet',
		]) {
			expect(within(section).getByText(term)).toBeInTheDocument()
		}
	})

	it('lists the model licenses with repository and license links', () => {
		render(Page)
		const section = screen.getByRole('region', { name: 'Model Licenses' })

		expect(
			within(section).getByText(/both licensed under the/)
		).toBeInTheDocument()
		expect(
			within(section).getByText(/not bundled with this application/)
		).toBeInTheDocument()
		expect(
			within(section).getByRole('link', { name: 'Qwen3 8B (MLX 4-bit)' })
		).toHaveAttribute('href', 'https://huggingface.co/Qwen/Qwen3-8B-MLX-4bit')
		expect(
			within(section).getByRole('link', {
				name: 'MOSS Music 8B Instruct (MLX 5-bit)',
			})
		).toHaveAttribute(
			'href',
			'https://huggingface.co/FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit'
		)
		expect(
			within(section).getByRole('link', { name: 'Apache License 2.0' })
		).toHaveAttribute('href', '/licenses/apache-2.0.txt')
	})
})
