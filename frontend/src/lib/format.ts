// Decimal units, matching Hugging Face.
const BYTE_UNITS = ['B', 'kB', 'MB', 'GB', 'TB']

export function formatBytes(bytes: number): string {
	let value = Math.max(bytes, 0)
	let unit = 0
	while (value >= 1000 && unit < BYTE_UNITS.length - 1) {
		value /= 1000
		unit++
	}
	return unit === 0
		? `${Math.round(value)} B`
		: `${value.toFixed(1)} ${BYTE_UNITS[unit]}`
}

export function formatSpeed(bytesPerSecond: number): string {
	return `${(Math.max(bytesPerSecond, 0) / 1_000_000).toFixed(1)} MB/s`
}

export function formatDuration(seconds: number | null): string {
	if (seconds === null) return 'Calculating...'
	const total = Math.max(Math.round(seconds), 0)
	const hours = Math.floor(total / 3600)
	const minutes = Math.floor((total % 3600) / 60)
	const secs = total % 60
	if (hours > 0) return `${hours}h ${minutes}m`
	if (minutes > 0) return `${minutes}m ${secs}s`
	return `${secs}s`
}
