import type { ModelDownload } from '#lib/api.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it } from 'vitest'
import ModelDownloadPanel from './ModelDownload.svelte'

function makeDownload(overrides: Partial<ModelDownload> = {}): ModelDownload {
	return {
		model: 'nvidia/music-flamingo-2601-hf',
		downloaded_bytes: 1_200_000_000,
		total_bytes: 4_800_000_000,
		bytes_per_second: 12_300_000,
		seconds_remaining: 80,
		...overrides,
	}
}

afterEach(cleanup)

describe('ModelDownload', () => {
	it('shows the friendly model name', () => {
		render(ModelDownloadPanel, { download: makeDownload() })

		expect(screen.getByText('Music Flamingo 2601')).toBeInTheDocument()
		expect(
			screen.queryByText('nvidia/music-flamingo-2601-hf')
		).not.toBeInTheDocument()
	})

	it('links to the model on Hugging Face', () => {
		render(ModelDownloadPanel, { download: makeDownload() })

		const link = screen.getByRole('link', {
			name: 'Open Music Flamingo 2601 on Hugging Face',
		})
		expect(link).toHaveAttribute(
			'href',
			'https://huggingface.co/nvidia/music-flamingo-2601-hf'
		)
		expect(link).toHaveAttribute('target', '_blank')
	})

	it('falls back to the id and its Hugging Face page for an unknown model', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ model: 'org/model' }),
		})

		expect(screen.getByText('org/model')).toBeInTheDocument()
		expect(
			screen.getByRole('link', { name: 'Open org/model on Hugging Face' })
		).toHaveAttribute('href', 'https://huggingface.co/org/model')
	})

	it('shows a labeled progress bar with the percentage', () => {
		render(ModelDownloadPanel, { download: makeDownload() })

		const bar = screen.getByRole('progressbar', {
			name: 'Downloading Music Flamingo 2601',
		})
		expect(bar).toHaveAttribute('aria-valuenow', '25')
		expect(screen.getByText('25%')).toBeInTheDocument()
	})

	it('shows the downloaded size, speed and time remaining', () => {
		render(ModelDownloadPanel, { download: makeDownload() })

		expect(screen.getByText(/1\.2 GB of 4\.8 GB/)).toBeInTheDocument()
		expect(screen.getByText(/12\.3 MB\/s/)).toBeInTheDocument()
		expect(screen.getByText(/1m 20s left/)).toBeInTheDocument()
	})

	it('shows Waiting... instead of the speed and time remaining while the speed is 0', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ bytes_per_second: 0, seconds_remaining: null }),
		})

		expect(screen.queryByText(/MB\/s/)).not.toBeInTheDocument()
		expect(screen.queryByText(/left/)).not.toBeInTheDocument()
		expect(screen.getByText(/Waiting\.\.\./)).toBeInTheDocument()
		expect(screen.getByText(/1\.2 GB of 4\.8 GB/)).toBeInTheDocument()
	})

	it('shows only the speed when the time remaining is unknown', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ seconds_remaining: null }),
		})

		expect(screen.getByText(/12\.3 MB\/s/)).toBeInTheDocument()
		expect(screen.queryByText(/left/)).not.toBeInTheDocument()
	})

	it('caps the percentage at 100', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ downloaded_bytes: 5_000_000_000 }),
		})

		expect(screen.getByText('100%')).toBeInTheDocument()
	})

	it('is indeterminate without a percentage when the total is unknown', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ total_bytes: null }),
		})

		const bar = screen.getByRole('progressbar')
		expect(bar).not.toHaveAttribute('aria-valuenow')
		expect(screen.queryByText(/%/)).not.toBeInTheDocument()
		expect(screen.queryByText(/ of /)).not.toBeInTheDocument()
		expect(screen.getByText(/1\.2 GB/)).toBeInTheDocument()
	})

	it('shows a pending model as waiting with an empty bar', () => {
		render(ModelDownloadPanel, {
			download: makeDownload({ downloaded_bytes: 0, bytes_per_second: 0 }),
			state: 'pending',
		})

		const bar = screen.getByRole('progressbar', {
			name: 'Waiting to download Music Flamingo 2601',
		})
		expect(bar).toHaveAttribute('aria-valuenow', '0')
		expect(screen.getByText(/Waiting/)).toBeInTheDocument()
		expect(screen.getByText(/4\.8 GB/)).toBeInTheDocument()
		expect(screen.queryByText(/%/)).not.toBeInTheDocument()
	})
})
