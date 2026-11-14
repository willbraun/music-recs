import type { ModelStatus } from '#lib/api.js'
import { cleanup, render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { downloadMissingModelsMock } = vi.hoisted(() => ({
	downloadMissingModelsMock: vi.fn(),
}))

vi.mock('$app/navigation', () => ({
	beforeNavigate: vi.fn(),
	goto: vi.fn(),
}))
vi.mock('#lib/modelCache.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/modelCache.svelte.js')>()),
	downloadMissingModels: downloadMissingModelsMock,
}))

import DiscardTasteDialog from '#lib/components/DiscardTasteDialog.svelte'
import { modelCache } from '#lib/modelCache.svelte.js'
import { clearTaste } from '#lib/taste.svelte.js'
import { cancelLeave } from '#lib/tasteDraft.svelte.js'
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
	cancelLeave()
	document.body.style.removeProperty('pointer-events')
})

describe('TasteModal', () => {
	it('omits the size when it is unknown', () => {
		render(TasteModal, { open: true })

		expect(screen.getByText(/this may take a while/)).toBeInTheDocument()
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

	describe('unsaved taste', () => {
		function renderModal() {
			render(DiscardTasteDialog)
			return render(TasteModal, { open: true })
		}

		async function typeTaste() {
			await userEvent.type(screen.getByLabelText('Anything else'), 'Jazz')
		}

		it('closes without asking when nothing was entered', async () => {
			renderModal()
			await userEvent.click(screen.getByRole('button', { name: 'Close' }))

			await waitFor(() =>
				expect(screen.queryByText('What music do you like?')).toBeNull()
			)
			expect(screen.queryByText('Discard unsaved changes?')).toBeNull()
		})

		it('asks before closing and keeps the modal on Keep editing', async () => {
			renderModal()
			await typeTaste()
			await userEvent.click(screen.getByRole('button', { name: 'Close' }))

			expect(await screen.findByText('Discard unsaved changes?')).toBeVisible()
			await userEvent.click(
				screen.getByRole('button', { name: 'Keep editing' })
			)

			await waitFor(() =>
				expect(screen.queryByText('Discard unsaved changes?')).toBeNull()
			)
			expect(screen.getByLabelText('Anything else')).toHaveValue('Jazz')
		})

		it('closes the modal once the user discards', async () => {
			renderModal()
			await typeTaste()
			await userEvent.click(screen.getByRole('button', { name: 'Close' }))
			await userEvent.click(
				await screen.findByRole('button', { name: 'Discard' })
			)

			await waitFor(() =>
				expect(screen.queryByText('What music do you like?')).toBeNull()
			)
		})
	})
})
