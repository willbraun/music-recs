import type { ModelStatus } from '#lib/api.js'
import { MODELS } from '#lib/models.js'
import { cleanup, render, screen, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ModelCard from './ModelCard.svelte'

const info = MODELS[1]

function makeStatus(overrides: Partial<ModelStatus> = {}): ModelStatus {
	return {
		id: info.id,
		downloaded: false,
		size_bytes: 16_500_000_000,
		download: null,
		...overrides,
	}
}

const onDownload = vi.fn()
const onRemove = vi.fn()

function renderCard(
	status: ModelStatus,
	props: { isBusy?: boolean; isRemoving?: boolean } = {}
) {
	return render(ModelCard, {
		info,
		status,
		isBusy: false,
		isRemoving: false,
		onDownload,
		onRemove,
		...props,
	})
}

beforeEach(() => {
	onDownload.mockReset()
	onRemove.mockReset()
})

afterEach(() => {
	cleanup()
	// The dialog locks pointer events on the body and unlocks it after its close animation.
	document.body.style.pointerEvents = ''
})

describe('ModelCard', () => {
	it('shows the name, purpose and size', () => {
		renderCard(makeStatus())

		expect(
			screen.getByRole('heading', { name: 'MOSS Music 8B Instruct' })
		).toBeInTheDocument()
		expect(screen.getByText(info.purpose)).toBeInTheDocument()
		expect(screen.getByText('16.5 GB')).toBeInTheDocument()
	})

	it('links to the model on Hugging Face in a new tab', () => {
		renderCard(makeStatus())

		const link = screen.getByRole('link', {
			name: 'Open MOSS Music 8B Instruct on Hugging Face',
		})
		expect(link).toHaveAttribute(
			'href',
			'https://huggingface.co/FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit'
		)
		expect(link).toHaveAttribute('target', '_blank')
	})

	it('shows an unknown size', () => {
		renderCard(makeStatus({ size_bytes: null }))

		expect(screen.getByText('Unknown')).toBeInTheDocument()
	})

	describe('not downloaded', () => {
		it('offers Download and nothing else', async () => {
			renderCard(makeStatus())

			expect(screen.getByText('Not downloaded')).toBeInTheDocument()
			expect(
				screen.queryByRole('button', { name: /Remove/ })
			).not.toBeInTheDocument()
			await userEvent.click(
				screen.getByRole('button', { name: 'Download MOSS Music 8B Instruct' })
			)
			expect(onDownload).toHaveBeenCalledOnce()
		})
	})

	describe('downloading', () => {
		const download = {
			state: 'downloading' as const,
			downloaded_bytes: 4_125_000_000,
			total_bytes: 16_500_000_000,
			bytes_per_second: 12_300_000,
			seconds_remaining: 1000,
			error: null,
		}

		it('shows the progress and hides the actions', () => {
			renderCard(makeStatus({ download }))

			expect(screen.getByText('Downloading')).toBeInTheDocument()
			expect(
				screen.getByRole('progressbar', {
					name: 'Downloading MOSS Music 8B Instruct',
				})
			).toHaveAttribute('aria-valuenow', '25')
			expect(screen.getByText(/12\.3 MB\/s/)).toBeInTheDocument()
			expect(screen.queryByRole('button')).not.toBeInTheDocument()
		})

		it('shows a queued model as waiting', () => {
			renderCard(
				makeStatus({
					download: { ...download, state: 'pending', downloaded_bytes: 0 },
				})
			)

			expect(screen.getByText('Queued')).toBeInTheDocument()
			expect(
				screen.getByRole('progressbar', {
					name: 'Waiting to download MOSS Music 8B Instruct',
				})
			).toHaveAttribute('aria-valuenow', '0')
		})
	})

	describe('failed', () => {
		it('shows the error and offers Retry', async () => {
			renderCard(
				makeStatus({
					download: {
						state: 'failed',
						downloaded_bytes: 0,
						total_bytes: null,
						bytes_per_second: 0,
						seconds_remaining: null,
						error: 'network down',
					},
				})
			)

			expect(screen.getByText('Download failed')).toBeInTheDocument()
			expect(screen.getByRole('alert')).toHaveTextContent('network down')
			await userEvent.click(
				screen.getByRole('button', { name: 'Retry MOSS Music 8B Instruct' })
			)
			expect(onDownload).toHaveBeenCalledOnce()
		})
	})

	describe('downloaded', () => {
		it('shows the status and offers Remove, not Download', () => {
			renderCard(makeStatus({ downloaded: true }))

			expect(screen.getByText('Downloaded')).toBeInTheDocument()
			expect(
				screen.queryByRole('button', { name: /Download|Retry/ })
			).not.toBeInTheDocument()
			expect(
				screen.getByRole('button', { name: 'Remove MOSS Music 8B Instruct' })
			).toBeEnabled()
		})

		it('removes only after confirming', async () => {
			renderCard(makeStatus({ downloaded: true }))
			await userEvent.click(
				screen.getByRole('button', { name: 'Remove MOSS Music 8B Instruct' })
			)

			const dialog = await screen.findByRole('dialog', {
				name: 'Remove MOSS Music 8B Instruct?',
			})
			expect(dialog).toHaveTextContent('16.5 GB')
			expect(onRemove).not.toHaveBeenCalled()

			await userEvent.click(
				within(dialog).getByRole('button', { name: 'Remove' })
			)

			expect(onRemove).toHaveBeenCalledOnce()
			expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
		})

		it('keeps the model when the confirmation is cancelled', async () => {
			renderCard(makeStatus({ downloaded: true }))
			await userEvent.click(
				screen.getByRole('button', { name: 'Remove MOSS Music 8B Instruct' })
			)

			await userEvent.click(
				within(await screen.findByRole('dialog')).getByRole('button', {
					name: 'Cancel',
				})
			)

			expect(onRemove).not.toHaveBeenCalled()
			expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
		})

		it('disables Remove with an explanation while a run or download is busy', () => {
			renderCard(makeStatus({ downloaded: true }), { isBusy: true })

			expect(
				screen.getByRole('button', { name: 'Remove MOSS Music 8B Instruct' })
			).toBeDisabled()
			expect(
				screen.getByText('Available once the current run or download finishes.')
			).toBeInTheDocument()
		})

		it('disables Remove and says so while it is being removed', () => {
			renderCard(makeStatus({ downloaded: true }), {
				isBusy: true,
				isRemoving: true,
			})

			expect(screen.getByRole('button', { name: /Remove/ })).toBeDisabled()
			expect(screen.getByText('Removing...')).toBeInTheDocument()
			expect(screen.queryByText(/Available once/)).not.toBeInTheDocument()
		})
	})
})
