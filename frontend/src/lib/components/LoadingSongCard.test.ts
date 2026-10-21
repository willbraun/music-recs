import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { afterEach, describe, expect, it } from 'vitest'
import LoadingSongCard from './LoadingSongCard.svelte'

const ART = 'https://coverartarchive.org/release-group/rg/front-500'
const THUMB = 'https://img.youtube.com/vi/abc/hqdefault.jpg'

function getImage(container: HTMLElement): HTMLImageElement | null {
	return container.querySelector('img')
}

afterEach(cleanup)

describe('LoadingSongCard', () => {
	it('is a busy region labeled with the song title', () => {
		render(LoadingSongCard, { title: 'Test Song', artist: 'Test Artist' })

		expect(screen.getByLabelText('Analyzing Test Song')).toHaveAttribute(
			'aria-busy',
			'true'
		)
	})

	it('shows the title and artist', () => {
		render(LoadingSongCard, { title: 'Test Song', artist: 'Test Artist' })

		expect(screen.getByText('Test Song')).toBeInTheDocument()
		expect(screen.getByText('Test Artist')).toBeInTheDocument()
	})

	it('shows the thumbnail', () => {
		const { container } = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
			thumbnailUrl: THUMB,
		})

		expect(getImage(container)).toHaveAttribute('src', THUMB)
	})

	it('prefers the album art over the thumbnail', () => {
		const { container } = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
			thumbnailUrl: THUMB,
			albumArtUrl: ART,
		})

		expect(getImage(container)).toHaveAttribute('src', ART)
	})

	it('falls back to the thumbnail when the album art fails to load', async () => {
		const { container } = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
			thumbnailUrl: THUMB,
			albumArtUrl: ART,
		})

		await fireEvent.error(getImage(container)!)

		expect(getImage(container)).toHaveAttribute('src', THUMB)
	})

	it('fades the image in once it has loaded', async () => {
		const { container } = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
			thumbnailUrl: THUMB,
		})
		expect(getImage(container)).toHaveClass('opacity-0')

		await fireEvent.load(getImage(container)!)

		expect(getImage(container)).toHaveClass('opacity-40')
	})

	it('shows only the spinner without a thumbnail or after it fails', async () => {
		const withoutThumbnail = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
		})
		expect(getImage(withoutThumbnail.container)).toBeNull()
		cleanup()

		const { container } = render(LoadingSongCard, {
			title: 'T',
			artist: 'A',
			thumbnailUrl: THUMB,
		})
		await fireEvent.error(getImage(container)!)

		expect(getImage(container)).toBeNull()
	})
})
