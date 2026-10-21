import '@testing-library/jest-dom/vitest'

// jsdom lacks ResizeObserver, which the Bits UI slider requires.
globalThis.ResizeObserver ??= class {
	observe() {}
	unobserve() {}
	disconnect() {}
}

// jsdom lacks scrollIntoView, which the Bits UI command list calls.
Element.prototype.scrollIntoView ??= () => {}
