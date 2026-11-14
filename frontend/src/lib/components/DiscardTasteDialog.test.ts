import { cancelLeave, tasteDraft } from '#lib/tasteDraft.svelte.js'
import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { gotoMock, navigationHook } = vi.hoisted(() => ({
	gotoMock: vi.fn(),
	navigationHook: { current: null as null | ((nav: unknown) => void) },
}))

vi.mock('$app/navigation', () => ({
	goto: gotoMock,
	beforeNavigate: (callback: (nav: unknown) => void) => {
		navigationHook.current = callback
	},
}))

import DiscardTasteDialog from './DiscardTasteDialog.svelte'

afterEach(() => {
	cleanup()
	cancelLeave()
	tasteDraft.isDirty = false
	gotoMock.mockReset()
})

function navigate(overrides: Record<string, unknown> = {}) {
	const cancel = vi.fn()
	navigationHook.current?.({
		cancel,
		to: { url: new URL('http://localhost/songs') },
		willUnload: false,
		...overrides,
	})
	return cancel
}

describe('DiscardTasteDialog', () => {
	it('lets navigation through when nothing is unsaved', () => {
		render(DiscardTasteDialog)

		expect(navigate()).not.toHaveBeenCalled()
	})

	it('holds navigation until the user discards', async () => {
		render(DiscardTasteDialog)
		tasteDraft.isDirty = true

		expect(navigate()).toHaveBeenCalledOnce()
		expect(await screen.findByText('Discard unsaved changes?')).toBeVisible()
		expect(gotoMock).not.toHaveBeenCalled()

		await userEvent.click(screen.getByRole('button', { name: 'Discard' }))

		expect(gotoMock).toHaveBeenCalledWith(new URL('http://localhost/songs'))
	})

	it('stays on the page after Keep editing', async () => {
		render(DiscardTasteDialog)
		tasteDraft.isDirty = true
		navigate()

		await userEvent.click(
			await screen.findByRole('button', { name: 'Keep editing' })
		)

		expect(gotoMock).not.toHaveBeenCalled()
		expect(tasteDraft.isDirty).toBe(true)
	})

	it('defers to the browser prompt on reload or external links', () => {
		render(DiscardTasteDialog)
		tasteDraft.isDirty = true

		expect(navigate({ willUnload: true, to: null })).toHaveBeenCalledOnce()
		expect(tasteDraft.pendingLeave).toBeNull()
	})
})
