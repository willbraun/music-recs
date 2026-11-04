import { cleanup, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it, vi } from 'vitest'
import NvidiaPage from './nvidia/+page.svelte'
import QwenPage from './qwen/+page.svelte'

type NavigationCallback = (navigation: { from: { url: URL } | null }) => void

const { afterNavigateMock } = vi.hoisted(() => ({
	afterNavigateMock: vi.fn<(callback: NavigationCallback) => void>(),
}))
vi.mock('$app/navigation', () => ({ afterNavigate: afterNavigateMock }))

afterEach(() => {
	cleanup()
	afterNavigateMock.mockReset()
})

describe('license pages', () => {
	it('renders the Qwen license text', () => {
		render(QwenPage)

		expect(
			screen.getByRole('heading', {
				name: 'Qwen Research License Agreement',
				level: 1,
			})
		).toBeInTheDocument()
		expect(
			screen.getByRole('heading', { name: '2. Grant of Rights' })
		).toBeInTheDocument()
	})

	it('renders the NVIDIA license text', () => {
		render(NvidiaPage)

		expect(
			screen.getByRole('heading', { name: 'NVIDIA License', level: 1 })
		).toBeInTheDocument()
		expect(screen.getByText(/means for academic purposes only/)).toBeVisible()
	})

	it('goes back to About after a direct visit', () => {
		render(QwenPage)

		expect(screen.getByRole('link', { name: 'Back' })).toHaveAttribute(
			'href',
			'/about'
		)
	})

	it('goes back to the page it was reached from', async () => {
		render(QwenPage)
		const link = screen.getByRole('link', { name: 'Back' })

		afterNavigateMock.mock.calls[0][0]({
			from: { url: new URL('http://localhost/models') },
		})

		await vi.waitFor(() => expect(link).toHaveAttribute('href', '/models'))
	})
})
