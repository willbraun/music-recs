import type { ModelStatus } from '#lib/api.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { downloadMissingModelsMock } = vi.hoisted(() => ({
	downloadMissingModelsMock: vi.fn(),
}))

vi.mock('#lib/modelCache.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/modelCache.svelte.js')>()),
	downloadMissingModels: downloadMissingModelsMock,
}))

import { modelCache } from '#lib/modelCache.svelte.js'
import { clearTaste } from '#lib/taste.svelte.js'
import TasteModal from './TasteModal.svelte'

function makeModel(
	id: string,
	overrides: Partial<ModelStatus> = {}
): ModelStatus {
	return {
		id,
		downloaded: false,
		size_bytes: null,
		download: null,
		...overrides,
	}
}

beforeEach(() => {
	downloadMissingModelsMock.mockReset().mockResolvedValue(undefined)
	clearTaste()
	modelCache.status = 'ready'
	modelCache.items = [makeModel('org/first'), makeModel('org/second')]
})

afterEach(() => {
	cleanup()
	document.body.style.removeProperty('pointer-events')
})

describe('TasteModal', () => {
	it('omits the size when it is unknown', () => {
		render(TasteModal, { open: true })

		expect(screen.getByText('this may take a while')).toBeInTheDocument()
		expect(screen.queryByText(/About/)).not.toBeInTheDocument()
	})

	it('shows a failed download with a retry button', async () => {
		modelCache.items = [
			makeModel('org/first', {
				download: {
					state: 'failed',
					downloaded_bytes: 0,
					total_bytes: null,
					bytes_per_second: 0,
					seconds_remaining: null,
					error: 'network down',
				},
			}),
			makeModel('org/second'),
		]
		render(TasteModal, { open: true })

		expect(screen.getByRole('alert')).toHaveTextContent(
			'org/first: network down'
		)
		await userEvent.click(
			screen.getByRole('button', { name: 'Retry Download' })
		)
		expect(downloadMissingModelsMock).toHaveBeenCalledOnce()
	})

	it('shows the models as ready when they finish while open', async () => {
		render(TasteModal, { open: true })
		expect(screen.queryByText('Models ready')).not.toBeInTheDocument()

		modelCache.items = modelCache.items.map((item) => ({
			...item,
			downloaded: true,
		}))

		expect(await screen.findByText('Models ready')).toBeInTheDocument()
		expect(
			screen.queryByRole('button', { name: 'Download Models' })
		).not.toBeInTheDocument()
	})

	it('shows no model section when the models were already downloaded', () => {
		modelCache.items = modelCache.items.map((item) => ({
			...item,
			downloaded: true,
		}))
		render(TasteModal, { open: true })

		expect(screen.queryByText('Models ready')).not.toBeInTheDocument()
		expect(screen.queryByText('Get ready to discover')).not.toBeInTheDocument()
	})
})
