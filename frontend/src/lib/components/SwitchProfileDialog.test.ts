import { cleanup, render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { gotoMock, confirmMock } = vi.hoisted(() => ({
	gotoMock: vi.fn(),
	confirmMock: vi.fn(async () => true),
}))

vi.mock('$app/navigation', () => ({ goto: gotoMock }))
vi.mock('#lib/profiles.svelte.js', async (importOriginal) => ({
	...(await importOriginal<typeof import('#lib/profiles.svelte.js')>()),
	confirmProfileSwitch: confirmMock,
}))

import { profiles } from '#lib/profiles.svelte.js'
import SwitchProfileDialog from './SwitchProfileDialog.svelte'

afterEach(() => {
	cleanup()
	profiles.pendingSwitchId = null
	document.body.style.pointerEvents = ''
	vi.clearAllMocks()
})

describe('SwitchProfileDialog', () => {
	it('is hidden until a switch is pending', () => {
		render(SwitchProfileDialog)

		expect(screen.queryByText('Switch profiles?')).toBeNull()
	})

	it('warns that the run will be cancelled and stays put on Stay', async () => {
		profiles.pendingSwitchId = 2
		render(SwitchProfileDialog)

		expect(await screen.findByText(/cancels the run/)).toBeInTheDocument()
		await userEvent.click(screen.getByRole('button', { name: 'Stay' }))

		expect(profiles.pendingSwitchId).toBeNull()
		expect(confirmMock).not.toHaveBeenCalled()
		expect(gotoMock).not.toHaveBeenCalled()
	})

	it('confirms the switch and opens Discover', async () => {
		profiles.pendingSwitchId = 2
		render(SwitchProfileDialog)

		await userEvent.click(
			await screen.findByRole('button', { name: 'Cancel and switch' })
		)

		await waitFor(() => expect(gotoMock).toHaveBeenCalledWith('/'))
		expect(confirmMock).toHaveBeenCalledOnce()
	})
})
