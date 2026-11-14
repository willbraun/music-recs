import svelte from 'eslint-plugin-svelte'
import tseslint from 'typescript-eslint'

// Only project-specific import rules; formatting is Prettier's job and types are svelte-check's.
export default tseslint.config(
	{ ignores: ['build/', '.svelte-kit/', 'src-tauri/'] },
	{ linterOptions: { reportUnusedDisableDirectives: 'off' } },
	...svelte.configs.base,
	{
		files: ['**/*.ts'],
		languageOptions: { parser: tseslint.parser },
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			parserOptions: { parser: tseslint.parser },
		},
	},
	{
		files: ['src/**/*.{ts,svelte}'],
		// Registered so existing `eslint-disable @typescript-eslint/*` comments resolve.
		plugins: { '@typescript-eslint': tseslint.plugin },
		rules: {
			'no-restricted-imports': [
				'error',
				{
					paths: [
						{
							name: '@lucide/svelte',
							importNames: ['X', 'XIcon'],
							message:
								"Use '#lib/components/icons/X.svelte'; Lucide's X has a gap in Safari/WebKit.",
						},
					],
					patterns: [
						{
							regex: '^@lucide/svelte/icons/(x|close)(\\.svelte|\\.js)?$',
							message:
								"Use '#lib/components/icons/X.svelte'; Lucide's X has a gap in Safari/WebKit.",
						},
					],
				},
			],
		},
	}
)
