import { cleanup, render, screen, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '#lib/api.js'
import ProfileForm from './ProfileForm.svelte'

afterEach(cleanup)

describe('ProfileForm', () => {
	it('cannot be submitted without a name', async () => {
		const user = userEvent.setup()
		const onsubmit = vi.fn()
		render(ProfileForm, { onsubmit, submitLabel: 'Create profile' })
		const submit = screen.getByRole('button', { name: 'Create profile' })

		expect(submit).toBeDisabled()
		await user.type(screen.getByLabelText('Name'), '   ')
		expect(submit).toBeDisabled()
		await user.type(screen.getByLabelText('Name'), 'Ann')
		expect(submit).toBeEnabled()
	})

	it('submits the trimmed name and the chosen emoji', async () => {
		const user = userEvent.setup()
		const onsubmit = vi.fn().mockResolvedValue(undefined)
		render(ProfileForm, { onsubmit })

		await user.type(screen.getByLabelText('Name'), '  Ann ')
		await user.click(screen.getByRole('radio', { name: 'Use 🦊 as avatar' }))
		await user.click(screen.getByRole('button', { name: 'Save' }))

		expect(onsubmit).toHaveBeenCalledWith({ name: 'Ann', avatar: '🦊' })
	})

	it('starts from the profile being edited and lets the avatar be typed', async () => {
		const user = userEvent.setup()
		const onsubmit = vi.fn().mockResolvedValue(undefined)
		render(ProfileForm, {
			profile: { id: 3, name: 'Bob', avatar: '🎹' },
			onsubmit,
		})

		expect(screen.getByLabelText('Name')).toHaveValue('Bob')
		await user.clear(screen.getByLabelText('Or type your own emoji'))
		await user.type(screen.getByLabelText('Or type your own emoji'), '🍉')
		await user.click(screen.getByRole('button', { name: 'Save' }))

		expect(onsubmit).toHaveBeenCalledWith({ name: 'Bob', avatar: '🍉' })
	})

	it('shows the API message when the avatar is rejected', async () => {
		const user = userEvent.setup()
		const onsubmit = vi
			.fn()
			.mockRejectedValue(new ApiError('Avatar must be an emoji', 422))
		render(ProfileForm, { onsubmit })

		await user.type(screen.getByLabelText('Name'), 'Ann')
		await user.click(screen.getByRole('button', { name: 'Save' }))

		expect(await screen.findByText('Avatar must be an emoji')).toBeVisible()
	})

	it('blocks saving a typed letter as the avatar', async () => {
		const user = userEvent.setup()
		const onsubmit = vi.fn()
		render(ProfileForm, { onsubmit })

		await user.type(screen.getByLabelText('Name'), 'Ann')
		await user.clear(screen.getByLabelText('Or type your own emoji'))
		await user.type(screen.getByLabelText('Or type your own emoji'), 'a')

		expect(screen.getByRole('alert')).toHaveTextContent(/must be an emoji/)
		expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
	})

	it('offers cancel only when there is somewhere to go back to', () => {
		const { unmount } = render(ProfileForm, { onsubmit: vi.fn() })
		expect(screen.queryByRole('link', { name: 'Cancel' })).toBeNull()
		unmount()

		render(ProfileForm, { onsubmit: vi.fn(), cancelHref: '/profiles' })
		expect(screen.getByRole('link', { name: 'Cancel' })).toHaveAttribute(
			'href',
			'/profiles'
		)
	})

	it('deletes only after confirmation', async () => {
		const user = userEvent.setup()
		const ondelete = vi.fn().mockResolvedValue(undefined)
		render(ProfileForm, {
			profile: { id: 3, name: 'Bob', avatar: '🎹' },
			onsubmit: vi.fn(),
			ondelete,
		})

		await user.click(screen.getByRole('button', { name: 'Delete profile' }))
		expect(ondelete).not.toHaveBeenCalled()
		await user.click(screen.getByRole('button', { name: 'Delete' }))

		await waitFor(() => expect(ondelete).toHaveBeenCalledOnce())
	})
})
