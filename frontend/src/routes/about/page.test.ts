import { cleanup, render, screen, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { checkForUpdatesMock } = vi.hoisted(() => ({
	checkForUpdatesMock: vi.fn(),
}))

vi.mock('#lib/update.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/update.svelte.js')>()),
	checkForUpdates: checkForUpdatesMock,
}))

import { update } from '#lib/update.svelte.js'
import Page from './+page.svelte'

afterEach(() => {
	cleanup()
	Object.assign(update, { status: 'idle', latestVersion: null, error: null })
})

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

	it('shows the app version, copyright and license link', () => {
		render(Page)

		expect(screen.getByText(/Version \d+\.\d+\.\d+/)).toBeInTheDocument()
		expect(screen.getByText(/© 2026 Will Braun/)).toBeInTheDocument()
		expect(screen.getByRole('link', { name: 'MIT License' })).toHaveAttribute(
			'href',
			'/licenses/mit.txt'
		)
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

	it('checks for updates when the button is pressed', async () => {
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'Check For Updates' })
		)

		expect(checkForUpdatesMock).toHaveBeenCalledTimes(1)
	})

	it('disables the button while checking', () => {
		update.status = 'checking'
		render(Page)

		expect(screen.getByRole('button', { name: 'Checking...' })).toBeDisabled()
	})

	it('shows the result of an update check', () => {
		update.status = 'up-to-date'
		const { unmount } = render(Page)
		expect(screen.getByRole('status')).toHaveTextContent("You're up to date.")
		unmount()

		Object.assign(update, { status: 'error', error: 'offline' })
		render(Page)
		expect(screen.getByRole('status')).toHaveTextContent(
			'Could not check for updates: offline'
		)
	})

	it('replaces the check button with a link to the release when an update is available', () => {
		Object.assign(update, { status: 'available', latestVersion: '0.2.0' })
		render(Page)

		const link = screen.getByRole('link', {
			name: 'Version 0.2.0 is available',
		})
		expect(link).toHaveAttribute(
			'href',
			'https://github.com/willbraun/music-recs/releases/latest'
		)
		expect(link).toHaveAttribute('target', '_blank')
		expect(
			screen.queryByRole('button', { name: 'Check For Updates' })
		).toBeNull()
	})
})
