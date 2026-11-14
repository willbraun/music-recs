import adapter from '@sveltejs/adapter-static'
import { sveltekit } from '@sveltejs/kit/vite'
import tailwindcss from '@tailwindcss/vite'
import { svelteTesting } from '@testing-library/svelte/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true,
			},

			adapter: adapter({ fallback: 'index.html' }),
		}),
		svelteTesting(),
	],
	server: {
		fs: {
			allow: ['..'],
		},
		proxy: {
			// The Python API from api/api.py; it does not serve the frontend. The run events stream is SSE.
			// The shorthand string form rewrites Host; the API needs the browser's Host to match its Origin.
			'/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
		},
	},
	test: {
		environment: 'jsdom',
		include: ['src/**/*.test.ts'],
		setupFiles: ['./src/vitest-setup.ts'],
	},
})
