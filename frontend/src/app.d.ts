// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	// Injected by vite.config.ts from src-tauri/Cargo.toml.
	const __APP_VERSION__: string

	interface ImportMetaEnv {
		// Dev only: treated as the latest release, to try the update notice.
		readonly VITE_UPDATE_TEST_VERSION?: string
	}

	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {}
