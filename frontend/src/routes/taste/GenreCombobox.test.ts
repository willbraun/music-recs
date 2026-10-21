import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import GenreCombobox from './GenreCombobox.svelte'

afterEach(cleanup)

function renderCombobox(selected: string[] = [], blocked: string[] = []) {
	render(GenreCombobox, {
		id: 'genres',
		label: 'Genres',
		selected,
		blocked,
		blockedHint: 'In your dislikes',
	})
	return screen.getByRole('combobox', { name: 'Genres' })
}

// jsdom has no layout, so the popover is visibility:hidden and option names compute to empty.
async function findOptions() {
	return screen.findAllByRole('option', { hidden: true })
}

async function findOption(text: string | RegExp) {
	const options = await findOptions()
	const match = options.find((option) =>
		typeof text === 'string'
			? option.textContent?.trim() === text
			: text.test(option.textContent ?? '')
	)
	if (!match) throw new Error(`No option matching ${text}`)
	return match
}

describe('GenreCombobox', () => {
	it('selects a genre from the list and keeps the list open', async () => {
		const trigger = renderCombobox()

		await userEvent.click(trigger)
		await userEvent.click(await findOption('Jazz'))

		expect(screen.getByRole('button', { name: 'Remove Jazz' })).toBeVisible()
		expect(trigger).toHaveAttribute('aria-expanded', 'true')
	})

	it('deselects a selected genre from the list', async () => {
		const trigger = renderCombobox(['Jazz'])

		await userEvent.click(trigger)
		await userEvent.click(await findOption('Jazz'))

		expect(
			screen.queryByRole('button', { name: 'Remove Jazz' })
		).not.toBeInTheDocument()
	})

	it('removes a genre with its badge button', async () => {
		renderCombobox(['Jazz', 'Funk'])

		await userEvent.click(screen.getByRole('button', { name: 'Remove Jazz' }))

		expect(
			screen.queryByRole('button', { name: 'Remove Jazz' })
		).not.toBeInTheDocument()
		expect(screen.getByRole('button', { name: 'Remove Funk' })).toBeVisible()
	})

	it('offers to add a genre that is not in the list', async () => {
		const trigger = renderCombobox()

		await userEvent.click(trigger)
		await userEvent.type(
			await screen.findByPlaceholderText('Search or add a genre'),
			'Dream pop'
		)
		await userEvent.click(await findOption('Add Dream pop'))

		expect(
			screen.getByRole('button', { name: 'Remove Dream pop' })
		).toBeVisible()
	})

	it('does not offer to add a genre that is already listed', async () => {
		const trigger = renderCombobox()

		await userEvent.click(trigger)
		await userEvent.type(
			await screen.findByPlaceholderText('Search or add a genre'),
			'jazz'
		)

		expect(screen.queryByText(/^Add /)).not.toBeInTheDocument()
	})

	it('disables a genre chosen in the opposite field', async () => {
		const trigger = renderCombobox([], ['Country'])

		await userEvent.click(trigger)
		const option = await findOption(/Country/)

		expect(option).toHaveAttribute('aria-disabled', 'true')
		expect(option).toHaveTextContent('In your dislikes')
	})

	it('disables adding a custom genre chosen in the opposite field', async () => {
		const trigger = renderCombobox([], ['Dream pop'])

		await userEvent.click(trigger)
		await userEvent.type(
			await screen.findByPlaceholderText('Search or add a genre'),
			'dream pop'
		)

		expect(await findOption(/Add dream pop/)).toHaveAttribute(
			'aria-disabled',
			'true'
		)
	})
})
