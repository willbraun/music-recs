import '@testing-library/jest-dom/vitest'

// jsdom lacks ResizeObserver, which the Bits UI slider requires.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
}
