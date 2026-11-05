import type { ModelStatus } from '#lib/api.js'
import { cleanup, render, screen, within } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const {
	downloadModelMock,
	loadModelCacheMock,
	removeModelFilesMock,
	watchModelCacheMock,
	modelCache,
} = vi.hoisted(() => ({
	downloadModelMock: vi.fn(),
	loadModelCacheMock: vi.fn(),
	removeModelFilesMock: vi.fn(),
	watchModelCacheMock: vi.fn(),
	modelCache: {
		status: 'loading',
		items: [] as unknown[],
		busy: false,
		error: null as string | null,
		removing: [] as string[],
	},
}))

vi.mock('#lib/modelCache.svelte.js', () => ({
	modelCache,
	downloadModel: downloadModelMock,
	loadModelCache: loadModelCacheMock,
	removeModelFiles: removeModelFilesMock,
	watchModelCache: watchModelCacheMock,
}))

import Page from './+page.svelte'

const QWEN = 'Qwen/Qwen2.5-3B-Instruct'
const MOSS = 'FractalSurfer/MOSS-Music-8B-Instruct-mlx-5bit'

function makeStatus(
	id: string,
	overrides: Partial<ModelStatus> = {}
): ModelStatus {
	return {
		id,
		downloaded: false,
		size_bytes: 1_000_000_000,
		download: null,
		...overrides,
	}
}

beforeEach(() => {
	downloadModelMock.mockReset()
	loadModelCacheMock.mockReset()
	removeModelFilesMock.mockReset()
	watchModelCacheMock.mockReset().mockReturnValue(() => {})
	modelCache.status = 'ready'
	modelCache.items = [
		makeStatus(QWEN, { downloaded: true }),
		makeStatus(MOSS),
	]
	modelCache.busy = false
	modelCache.error = null
	modelCache.removing = []
})

afterEach(cleanup)

describe('models page', () => {
	it('shows the heading and both models', () => {
		render(Page)

		expect(
			screen.getByRole('heading', { name: 'Models', level: 1 })
		).toBeInTheDocument()
		expect(
			screen.getByRole('heading', { name: 'Qwen 2.5 3B Instruct' })
		).toBeInTheDocument()
		expect(
			screen.getByRole('heading', { name: 'MOSS Music 8B Instruct' })
		).toBeInTheDocument()
		expect(screen.getByText('Downloaded')).toBeInTheDocument()
		expect(screen.getByText('Not downloaded')).toBeInTheDocument()
	})

	it('watches the models while mounted and stops on unmount', () => {
		const stopWatching = vi.fn()
		watchModelCacheMock.mockReturnValue(stopWatching)
		const { unmount } = render(Page)

		expect(watchModelCacheMock).toHaveBeenCalledOnce()
		unmount()
		expect(stopWatching).toHaveBeenCalledOnce()
	})

	it('shows a loading state', () => {
		modelCache.status = 'loading'
		modelCache.items = []
		render(Page)

		expect(screen.getByLabelText('Loading models')).toHaveAttribute(
			'aria-busy',
			'true'
		)
		expect(screen.queryByRole('heading', { level: 2 })).not.toBeInTheDocument()
	})

	it('shows the error with Retry', async () => {
		modelCache.status = 'error'
		modelCache.error = 'Request failed (500)'
		render(Page)

		expect(screen.getByText('Request failed (500)')).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

		expect(loadModelCacheMock).toHaveBeenCalledOnce()
	})

	it('downloads the model whose button was clicked', async () => {
		render(Page)

		await userEvent.click(
			screen.getByRole('button', { name: 'Download MOSS Music 8B Instruct' })
		)

		expect(downloadModelMock).toHaveBeenCalledWith(MOSS)
	})

	it('removes the model after confirming', async () => {
		render(Page)
		await userEvent.click(
			screen.getByRole('button', { name: 'Remove Qwen 2.5 3B Instruct' })
		)
		const dialog = await screen.findByRole('dialog')
		await userEvent.click(
			within(dialog).getByRole('button', { name: 'Remove' })
		)

		expect(removeModelFilesMock).toHaveBeenCalledWith(QWEN)
	})

	it('disables removal while the API is busy', () => {
		modelCache.busy = true
		render(Page)

		expect(
			screen.getByRole('button', { name: 'Remove Qwen 2.5 3B Instruct' })
		).toBeDisabled()
	})

	it('skips a model the page has no details for', () => {
		modelCache.items = [makeStatus('org/unknown'), makeStatus(MOSS)]
		render(Page)

		expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(1)
	})
})
