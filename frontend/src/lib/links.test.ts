import { afterEach, describe, expect, it, vi } from 'vitest'
import {
	buildAppleMusicSearchUrl,
	handleExternalLinkClick,
	openExternalUrl,
} from './links.js'

const { openUrlMock } = vi.hoisted(() => ({ openUrlMock: vi.fn() }))
vi.mock('@tauri-apps/plugin-opener', () => ({ openUrl: openUrlMock }))

afterEach(() => {
	delete (window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
	openUrlMock.mockReset()
	vi.restoreAllMocks()
})

function enableTauri() {
	;(window as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__ = {}
}

function clickLink(attributes: string): MouseEvent {
	document.body.innerHTML = `<a ${attributes}><span>link</span></a>`
	const event = new MouseEvent('click', { bubbles: true, cancelable: true })
	document.body.addEventListener('click', handleExternalLinkClick, {
		once: true,
	})
	document.querySelector('span')!.dispatchEvent(event)
	return event
}

describe('buildAppleMusicSearchUrl', () => {
	it('searches the US storefront for the artist and title', () => {
		expect(
			buildAppleMusicSearchUrl({ artist: 'Radiohead', title: 'Weird Fishes' })
		).toBe('https://music.apple.com/us/search?term=Radiohead%20Weird%20Fishes')
	})

	it('encodes characters that would break the query string', () => {
		const url = new URL(
			buildAppleMusicSearchUrl({
				artist: 'Simon & Garfunkel',
				title: 'Weird Fishes/Arpeggi? #1',
			})
		)

		expect(url.searchParams.get('term')).toBe(
			'Simon & Garfunkel Weird Fishes/Arpeggi? #1'
		)
		expect(url.hash).toBe('')
	})

	it('keeps non-ASCII characters intact after decoding', () => {
		const url = new URL(
			buildAppleMusicSearchUrl({ artist: 'Björk', title: 'Jóga' })
		)

		expect(url.searchParams.get('term')).toBe('Björk Jóga')
	})
})

describe('openExternalUrl', () => {
	it('uses the opener plugin inside the desktop app', async () => {
		enableTauri()
		await openExternalUrl('https://example.com/')
		expect(openUrlMock).toHaveBeenCalledWith('https://example.com/')
	})

	it('opens a new window in the browser', async () => {
		const open = vi.spyOn(window, 'open').mockReturnValue(null)
		await openExternalUrl('https://example.com/')
		expect(open).toHaveBeenCalledWith(
			'https://example.com/',
			'_blank',
			'noopener,noreferrer'
		)
		expect(openUrlMock).not.toHaveBeenCalled()
	})
})

describe('handleExternalLinkClick', () => {
	it('opens target=_blank links through the opener in the desktop app', () => {
		enableTauri()
		const event = clickLink('href="https://example.com/a" target="_blank"')
		expect(event.defaultPrevented).toBe(true)
		expect(openUrlMock).toHaveBeenCalledWith('https://example.com/a')
	})

	it('leaves internal links and non-http links alone', () => {
		enableTauri()
		expect(clickLink('href="/songs"').defaultPrevented).toBe(false)
		expect(
			clickLink('href="mailto:a@b.c" target="_blank"').defaultPrevented
		).toBe(false)
		expect(openUrlMock).not.toHaveBeenCalled()
	})

	it('does nothing in the browser, where target=_blank works natively', () => {
		const event = clickLink('href="https://example.com/a" target="_blank"')
		expect(event.defaultPrevented).toBe(false)
		expect(openUrlMock).not.toHaveBeenCalled()
	})
})
