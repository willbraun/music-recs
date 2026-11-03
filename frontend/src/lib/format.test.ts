import { describe, expect, it } from 'vitest'
import { formatBytes, formatDuration, formatSpeed } from './format'

describe('formatBytes', () => {
	it.each([
		[0, '0 B'],
		[999, '999 B'],
		[1000, '1.0 kB'],
		[1_500_000, '1.5 MB'],
		[1_200_000_000, '1.2 GB'],
		[4_800_000_000, '4.8 GB'],
		[2_000_000_000_000, '2.0 TB'],
	])('formats %d as %s', (bytes, text) => {
		expect(formatBytes(bytes)).toBe(text)
	})
})

describe('formatSpeed', () => {
	it.each([
		[0, '0.0 MB/s'],
		[12_340_000, '12.3 MB/s'],
	])('formats %d as %s', (bytesPerSecond, text) => {
		expect(formatSpeed(bytesPerSecond)).toBe(text)
	})
})

describe('formatDuration', () => {
	it.each([
		[0, '0s'],
		[45.4, '45s'],
		[80, '1m 20s'],
		[65, '1m 5s'],
		[3600, '1h 0m'],
		[3900, '1h 5m'],
	])('formats %d seconds as %s', (seconds, text) => {
		expect(formatDuration(seconds)).toBe(text)
	})

	it('shows Calculating... when the time is unknown', () => {
		expect(formatDuration(null)).toBe('Calculating...')
	})
})
