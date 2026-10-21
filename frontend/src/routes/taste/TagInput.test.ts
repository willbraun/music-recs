import { cleanup, render, screen } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import TagInput from './TagInput.svelte'

afterEach(cleanup)

function renderInput(items: string[] = [], blocked: string[] = []) {
	render(TagInput, {
		id: 'artists',
		label: 'Artists',
		items,
		blocked,
		blockedMessage: 'Already in your dislikes',
	})
	return screen.getByLabelText('Artists')
}

describe('TagInput', () => {
	it('adds the typed name on Enter and clears the field', async () => {
		const input = renderInput()

		await userEvent.type(input, 'Tame Impala{Enter}')

		expect(screen.getByText('Tame Impala')).toBeInTheDocument()
		expect(input).toHaveValue('')
	})

	it('keeps commas inside a name', async () => {
		const input = renderInput()

		await userEvent.type(input, 'Earth, Wind & Fire{Enter}')

		expect(screen.getByText('Earth, Wind & Fire')).toBeInTheDocument()
	})

	it('ignores empty input', async () => {
		const input = renderInput()

		await userEvent.type(input, '   {Enter}')

		expect(screen.queryByRole('list')).not.toBeInTheDocument()
	})

	it('removes the last chip on Backspace in the empty field', async () => {
		const input = renderInput(['Flume', 'Tame Impala'])

		await userEvent.type(input, '{Backspace}')

		expect(screen.queryByText('Tame Impala')).not.toBeInTheDocument()
		expect(screen.getByText('Flume')).toBeInTheDocument()
	})

	it('removes a chip with its remove button', async () => {
		renderInput(['Flume', 'Tame Impala'])

		await userEvent.click(screen.getByRole('button', { name: 'Remove Flume' }))

		expect(screen.queryByText('Flume')).not.toBeInTheDocument()
		expect(screen.getByText('Tame Impala')).toBeInTheDocument()
	})

	it('does nothing for a duplicate, ignoring case', async () => {
		const input = renderInput(['Flume'])

		await userEvent.type(input, 'flume{Enter}')

		expect(screen.getAllByRole('listitem')).toHaveLength(1)
		expect(input).toHaveValue('flume')
	})

	it('rejects a name from the opposite list with a message', async () => {
		const input = renderInput([], ['Drake'])

		await userEvent.type(input, 'drake{Enter}')

		expect(screen.getByText('Already in your dislikes')).toBeInTheDocument()
		expect(screen.queryByRole('list')).not.toBeInTheDocument()
	})

	it('adds one chip per line when pasting multiple lines', async () => {
		const input = renderInput()

		await userEvent.click(input)
		await userEvent.paste('Flume\nTame Impala\n\nFlume')

		expect(screen.getAllByRole('listitem')).toHaveLength(2)
		expect(screen.getByText('Tame Impala')).toBeInTheDocument()
	})

	it('announces additions and removals', async () => {
		const input = renderInput()

		await userEvent.type(input, 'Flume{Enter}')
		expect(screen.getByText('Added Flume')).toHaveAttribute(
			'aria-live',
			'polite'
		)

		await userEvent.click(screen.getByRole('button', { name: 'Remove Flume' }))
		expect(screen.getByText('Removed Flume')).toBeInTheDocument()
	})
})
